import math
import os
import re
from datetime import datetime, date
from rembg import remove
from PIL import Image
import io
import joblib
from sklearn.linear_model import LogisticRegression

import numpy as np
import pandas as pd
import io

import urllib3
from flask import Flask, redirect, render_template, request, url_for, session, flash, send_file, Response
from flask_mysqldb import MySQL
from flask import send_from_directory
from flask_cors import CORS
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report

import requests

import platform

from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'evaluationsystem'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
UPLOAD_FOLDER = 'static/signatures'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# if not in deployment
if platform.system() == "Windows":
    # app.config['MYSQL_HOST'] = 'mysql-76692-0.cloudclusters.net';
    # app.config['MYSQL_USER'] = 'dbuser';
    # app.config['MYSQL_PASSWORD'] = 'dbuser123';
    # app.config['MYSQL_DB'] = 'isent';
    # app.config['MYSQL_PORT'] = 14859;
    app.config['MYSQL_HOST'] = 'localhost'
    app.config['MYSQL_USER'] = 'root'
    app.config['MYSQL_PASSWORD'] = 'jules0019'
    app.config['MYSQL_DB'] = 'isent'
# in deployment
else:
    app.config['MYSQL_HOST'] = 'mysql-178156-0.cloudclusters.net'
    app.config['MYSQL_USER'] = 'jules'
    app.config['MYSQL_PASSWORD'] = 'jules0019'
    app.config['MYSQL_DB'] = 'isent'
    app.config['MYSQL_PORT'] = 10019

    #old-db
    #app.config['MYSQL_HOST'] = 'mysql-76692-0.cloudclusters.net';
    #app.config['MYSQL_USER'] = 'dbuser';
    #app.config['MYSQL_PASSWORD'] = 'dbuser123';
    #app.config['MYSQL_DB'] = 'isent';
    #app.config['MYSQL_PORT'] = 14859;

mysql = MySQL(app)

cors = CORS(app)


G_TEACHER_ID = None
G_SUBJECT_ID = None
G_TEACHER_NAME = None
G_SUBJECT_NAME = None
G_NUMBER_OF_RESPONDENTS = None
G_EVALUATION_FORM_ID = None
G_CATEGORY_EMPLOYEE_ID = None
G_SCHOOL_ID = None
G_DEPARTMENT_ID = None
G_CATEGORY_NAME = None

@app.route('/logout', methods=["POST", "GET"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route('/', methods=["POST", "GET"])
@app.route("/login", methods=["POST", "GET"])
def login():
    session.pop('error', None)
    if 'logged_in' in session and session['logged_in']:
        cur = mysql.connection.cursor()
        sql = "SELECT role_id FROM users WHERE idnumber = %s"
        idnumber = session['idnumber']
        val = (idnumber,)
        cur.execute(sql, val)
        result = cur.fetchone()
        session['role_id'] = result[0]
        session['logged_in'] = True
        sql = "SELECT id FROM users WHERE idnumber = %s"
        val = (session['idnumber'],)
        cur.execute(sql, val)
        result = cur.fetchone()
        session['userId'] = result[0]

        cur.execute("SELECT * FROM users where idnumber = %s", (idnumber,))
        user = cur.fetchone()
        session['department_id'] = user[6]
        session['school_id'] = user[7]
        session['category_id'] = user[8]


        cur.close()

        return redirect(url_for("dashboard"))
    if request.method == "POST":
        idNumber = request.form.get('idnumber')
        password = request.form.get('password')

        cur = mysql.connection.cursor()
        sql = "SELECT password FROM users WHERE idnumber = %s"
        val = (idNumber,)
        cur.execute(sql, val)
        result = cur.fetchone()

        if result and result[0] == password:
            sql = "SELECT role_id FROM users WHERE idnumber = %s"
            val = (idNumber,)
            cur.execute(sql, val)
            result = cur.fetchone()
            session['role_id'] = result[0]
            session['logged_in'] = True
            session['idnumber'] = idNumber
            sql = "SELECT id FROM users WHERE idnumber = %s"
            val = (idNumber,)
            cur.execute(sql, val)
            result = cur.fetchone()
            session['userId'] = result[0]
            cur.execute("SELECT * FROM users where idnumber = %s", (idNumber,))
            user = cur.fetchone()
            session['department_id'] = user[6]
            session['school_id'] = user[7]
            session['category_id'] = user[8]

            cur.close()
            return redirect(url_for("dashboard"))
        else:
            session["error"] = "Invalid ID number or password"
            cur.close()
            return render_template("login.html")
    else:
        return render_template("login.html")


@app.route("/dashboard", methods = ["POST", "GET"])
def dashboard():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    category_name = None
    userId = session["userId"]
    roleId = session["role_id"]

    cur = mysql.connection.cursor()
    sql = "SELECT firstName FROM users WHERE id = %s"
    val = (session['userId'],)
    cur.execute(sql, val)
    firstName = cur.fetchall()
    sql = "SELECT roles.roleName FROM roles JOIN users ON users.role_id=roles.id WHERE users.id = %s"
    val = (session['userId'],)
    cur.execute(sql, val)
    roleName = cur.fetchall()

    cur.execute("SELECT * FROM department WHERE id <> 2 and id <> 3")
    college_departments = cur.fetchall()

    if roleName[0][0] != "SUPER ADMIN":
        cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s",
                    (session['school_id'], session['department_id']))
        questionnairesets = cur.fetchall()
        if len(questionnairesets) == 0:
            questionnairesets = [0, 0]
        questionnairesets = tuple(questionnairesets)
    else:
        cur.execute("SELECT id FROM questionnaireset")
        questionnairesets = cur.fetchall()
        if len(questionnairesets) == 0:
            questionnairesets = [0, 0]
        questionnairesets = tuple(questionnairesets)

    sql = "SELECT * FROM evaluationForms WHERE questionnaireset_id IN %s"
    cur.execute(sql, (questionnairesets,))
    evaluationsAll = cur.fetchall()
    evaluations = []
    doneEvaluations = []
    for evaluation in evaluationsAll:
        cur.execute("SELECT * FROM studentsubjects WHERE student_id = %s", (userId,))
        studentSubjects = cur.fetchall()
        takenAll = True
        for subject in studentSubjects:
            cur.execute("SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
                        (evaluation[0], userId, subject[2]))
            res = cur.fetchone()
            if res is None:
                takenAll = False
                break

        if not takenAll:
            evaluations.append(evaluation)

        if takenAll:
            doneEvaluations.append(evaluation)

    # print(len(evaluations))
    print("done", doneEvaluations)
    cur.execute("SELECT * FROM schoolyear")
    schoolyear = cur.fetchall()

    if roleId == 3:
        cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s", (session['school_id'], session['department_id']))
        questionnairesets = cur.fetchall()
        if len(questionnairesets) == 0:
            questionnairesets = (0,0)
        print(type(questionnairesets))
        sql = "SELECT * FROM evaluationForms WHERE questionnaireset_id IN %s"
        cur.execute(sql, (questionnairesets,))
        evaluationsAll = cur.fetchall()
        evaluations = []
        for evaluation in evaluationsAll:
            cur.execute("SELECT id FROM users WHERE school_id = %s and department_id = %s", (session['school_id'], session['department_id']))
            teachers_id = cur.fetchall()
            if len(teachers_id) == 0:
                teachers_id = [0,0]
                teachers_id = tuple(teachers_id)

            cur.execute("SELECT * FROM subjects WHERE teacherId in %s", (teachers_id,))
            subjects = cur.fetchall()
            takenAll = True
            for subject in subjects:
                cur.execute(
                    "SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
                    (evaluation[0], userId, subject[0]))
                res = cur.fetchone()
                if res is None:
                    takenAll = False
                    break
            evaluation = list(evaluation)
            if not takenAll:
                evaluation.append("NOT")
            else:
                evaluation.append("TAKEN")
            evaluations.append(evaluation)
        # evaluations = evaluationsAll
    elif roleId == 2:
        cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s",
                    (session['school_id'], session['department_id']))
        questionnairesets = cur.fetchall()
        if len(questionnairesets) == 0:
            questionnairesets = (0, 0)
        print(type(questionnairesets))
        sql = "SELECT * FROM evaluationForms WHERE questionnaireset_id IN %s"
        cur.execute(sql, (questionnairesets,))
        evaluationsAll = cur.fetchall()
        evaluations = []
        for evaluation in evaluationsAll:
            cur.execute("SELECT * FROM subjects")
            subjects = cur.fetchall()
            takenAll = True
            for subject in subjects:
                cur.execute(
                    "SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
                    (evaluation[0], userId, subject[0]))
                res = cur.fetchone()
                if res is None:
                    takenAll = False
                    break
            evaluation = list(evaluation)
            if not takenAll:
                evaluations.append(evaluation)
        # evaluations = evaluationsAll
        # employee_category_id = G_CATEGORY_EMPLOYEE_ID
        cur.execute("SELECT * FROM users where id = %s", (userId,))
        user = cur.fetchone()
        print(user)
        category_id = user[8]
        cur.execute("SELECT * FROM employeecategory WHERE id = %s", (category_id,))
        category = cur.fetchone()
        category_name = category[1]

    print(evaluations)
    cur.close()
    school_year = 1
    semester = 1

    if request.method == "POST":
        school_year = request.form.get('schoolYear')
        semester = request.form.get('semester')
        department = request.form.get('department')
        college_department = request.form.get('collegeDepartment', None)  # Only available if department is college
        cur = mysql.connection.cursor()

        departmentName = department

        cur.execute("SELECT * FROM department WHERE id <> 2 and id <> 3")
        college_departments = cur.fetchall()

        if roleName[0][0] != "SUPER ADMIN":
            cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s",
                        (session['school_id'], session['department_id']))
            questionnairesets = cur.fetchall()
            if len(questionnairesets) == 0:
                questionnairesets = [0, 0]
            questionnairesets = tuple(questionnairesets)
        else:
            if department == "college":
                departmentName = department
                department = college_department
            cur.execute("SELECT id FROM questionnaireset WHERE department_id = %s",
                        (department,))
            questionnairesets = cur.fetchall()
            if len(questionnairesets) == 0:
                questionnairesets = [0, 0]
            questionnairesets = tuple(questionnairesets)

        sql = "SELECT * FROM evaluationForms WHERE questionnaireset_id IN %s and semester_id = %s and schoolyear_id = %s"
        cur.execute(sql, (questionnairesets, semester, school_year))
        evaluationsAll = cur.fetchall()
        evaluations = []
        doneEvaluations = []
        for evaluation in evaluationsAll:
            cur.execute("SELECT * FROM studentsubjects WHERE student_id = %s", (userId,))
            studentSubjects = cur.fetchall()
            takenAll = True
            for subject in studentSubjects:
                cur.execute(
                    "SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
                    (evaluation[0], userId, subject[2]))
                res = cur.fetchone()
                if res is None:
                    takenAll = False
                    break

            if not takenAll:
                evaluations.append(evaluation)

            if takenAll:
                doneEvaluations.append(evaluation)

        # print(len(evaluations))
        print("done", doneEvaluations)

        if roleId == 3:
            cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s",
                        (session['school_id'], session['department_id']))
            questionnairesets = cur.fetchall()
            if len(questionnairesets) == 0:
                questionnairesets = (0, 0)
            print(type(questionnairesets))
            print(semester, school_year)
            sql = "SELECT * FROM evaluationForms WHERE questionnaireset_id IN %s and semester_id = %s and schoolyear_id = %s"
            cur.execute(sql, (questionnairesets, semester, school_year))
            evaluationsAll = cur.fetchall()
            evaluations = []
            for evaluation in evaluationsAll:
                cur.execute("SELECT id FROM users WHERE school_id = %s and department_id = %s",
                            (session['school_id'], session['department_id']))
                teachers_id = cur.fetchall()
                if len(teachers_id) == 0:
                    teachers_id = [0, 0]
                    teachers_id = tuple(teachers_id)

                cur.execute("SELECT * FROM subjects WHERE teacherId in %s", (teachers_id,))
                subjects = cur.fetchall()
                takenAll = True
                for subject in subjects:
                    cur.execute(
                        "SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
                        (evaluation[0], userId, subject[0]))
                    res = cur.fetchone()
                    if res is None:
                        takenAll = False
                        break
                evaluation = list(evaluation)
                if not takenAll:
                    evaluation.append("NOT")
                else:
                    evaluation.append("TAKEN")
                evaluations.append(evaluation)
            # evaluations = evaluationsAll
        elif roleId == 2:
            cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s",
                        (session['school_id'], session['department_id']))
            questionnairesets = cur.fetchall()
            if len(questionnairesets) == 0:
                questionnairesets = (0, 0)
            print(type(questionnairesets))
            sql = "SELECT * FROM evaluationForms WHERE questionnaireset_id IN %s and semester_id = %s and schoolyear_id = %s"
            cur.execute(sql, (questionnairesets, semester, school_year))
            evaluationsAll = cur.fetchall()
            evaluations = []
            for evaluation in evaluationsAll:
                cur.execute("SELECT * FROM subjects")
                subjects = cur.fetchall()
                takenAll = True
                for subject in subjects:
                    cur.execute(
                        "SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
                        (evaluation[0], userId, subject[0]))
                    res = cur.fetchone()
                    if res is None:
                        takenAll = False
                        break
                evaluation = list(evaluation)
                if not takenAll:
                    evaluations.append(evaluation)
            # evaluations = evaluationsAll
            # employee_category_id = G_CATEGORY_EMPLOYEE_ID
            cur.execute("SELECT * FROM users where id = %s", (userId,))
            user = cur.fetchone()
            print(user)
            category_id = user[8]
            cur.execute("SELECT * FROM employeecategory WHERE id = %s", (category_id,))
            category = cur.fetchone()
            category_name = category[1]

        print(evaluations)
        cur.close()
        return render_template("dashboard.html", departmentId=college_department, department=departmentName, school_year = school_year, semester=semester, schoolyear=schoolyear, doneEvaluations=doneEvaluations, departments=college_departments, evaluations=evaluations, firstName=firstName, roleName=roleName, categoryName=category_name)
    else:
        return render_template("dashboard.html",school_year = school_year, semester=semester, schoolyear=schoolyear, doneEvaluations=doneEvaluations, departments=college_departments, evaluations=evaluations, firstName=firstName, roleName=roleName, categoryName=category_name)

@app.route('/viewEvaluationStatistics/<evaluationFormId>', methods=['GET'])
def viewEvaluationStatistics(evaluationFormId):
    if 'userId' not in session:
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM evaluationForms WHERE id = %s", (evaluationFormId,))
    evaluationForm = cur.fetchone()

    evaluationName = evaluationForm[1]
    questionnaireset_id = evaluationForm[4]
    semester_id = evaluationForm[5]
    schoolyear_id = evaluationForm[6]

    cur.execute("SELECT department_id FROM questionnaireset WHERE id = %s", (questionnaireset_id,))
    department_id = cur.fetchone()[0]
    cur.execute("SELECT name FROM department WHERE id = %s", (department_id,))
    department = cur.fetchone()[0]

    cur.execute("SELECT semester FROM semester WHERE id = %s", (semester_id,))
    semester = cur.fetchone()[0]
    
    cur.execute("SELECT schoolyear FROM schoolyear WHERE id = %s", (schoolyear_id,))
    school_year = cur.fetchone()[0]

    cur.execute("SELECT id FROM users WHERE department_id = %s AND role_id = 1", (department_id,))
    # Number of respondents and those who did not
    userIds_in_department = cur.fetchall()
    responded = 0
    notResponded = 0
    for id in userIds_in_department:
        cur.execute("SELECT subject_id FROM studentsubjects WHERE student_id = %s", (id,))
        studentsSubjectIds = cur.fetchall()
        takenAll = True
        for subjectId in studentsSubjectIds:
            cur.execute("SELECT * FROM evaluation WHERE idstudent = %s and subject_id = %s and evaluationform_id = %s", (id, subjectId, evaluationFormId))
            res = cur.fetchall()
            if not res:
                notResponded += 1
                takenAll = False
                break
        if takenAll:
            responded += 1

    respondent_data = [responded, notResponded]
    # Sentiment data for full-time and part-time
    cur.execute("SELECT id FROM users WHERE department_id = %s and employeecategory_id = 1", (department_id,))
    fulltime_ids = cur.fetchall()
    if not fulltime_ids:
        fulltime_ids = (0,)

    cur.execute("SELECT AVG(pos) FROM evaluation WHERE evaluationForm_id = %s and idteacher in %s", (evaluationFormId, fulltime_ids))
    positive_fullTime = cur.fetchone()[0]
    if positive_fullTime is None:
        positive_fullTime = 0
    cur.execute("SELECT AVG(neu) FROM evaluation WHERE evaluationForm_id = %s and idteacher in %s", (evaluationFormId, fulltime_ids))
    neutral_fullTime = cur.fetchone()[0]
    if neutral_fullTime is None:
        neutral_fullTime = 0
    cur.execute("SELECT AVG(neg) FROM evaluation WHERE evaluationForm_id = %s and idteacher in %s", (evaluationFormId, fulltime_ids))
    negative_fullTime = cur.fetchone()[0]
    if negative_fullTime is None:
        negative_fullTime = 0

    cur.execute("SELECT id FROM users WHERE department_id = %s and employeecategory_id = 2", (department_id,))
    parttime_ids = cur.fetchall()
    if not parttime_ids:
        parttime_ids = (0,)
    cur.execute("SELECT AVG(pos) FROM evaluation WHERE evaluationForm_id = %s and idteacher in %s",
                (evaluationFormId, parttime_ids))
    positive_partTime = cur.fetchone()[0]
    if positive_partTime is None:
        positive_partTime = 0
    cur.execute("SELECT AVG(neu) FROM evaluation WHERE evaluationForm_id = %s and idteacher in %s",
                (evaluationFormId, parttime_ids))
    neutral_partTime = cur.fetchone()[0]
    if neutral_partTime is None:
        neutral_partTime = 0
    cur.execute("SELECT AVG(neg) FROM evaluation WHERE evaluationForm_id = %s and idteacher in %s",
                (evaluationFormId, parttime_ids))
    negative_partTime = cur.fetchone()[0]
    if negative_partTime is None:
        negative_partTime = 0



    full_time_sentiment_data = [positive_fullTime, negative_fullTime, neutral_fullTime]  # Example: Positive, Negative, Neutral for full-time
    part_time_sentiment_data = [positive_partTime, negative_partTime, neutral_partTime]  # Example: Positive, Negative, Neutral for part-time

    cur.execute("SELECT count(*) FROM users WHERE employeecategory_id = 1 and department_id = %s", (department_id,))
    full_time_count = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM users WHERE employeecategory_id = 2 and department_id = %s", (department_id,))
    part_time_count = cur.fetchone()[0]

    full_part_time_data = [full_time_count, part_time_count]

    cur.close()
    return render_template("viewEvaluationStatistics.html", department=department, semester=semester,
                           school_year=school_year, respondent_data=respondent_data,
                           full_time_sentiment_data=full_time_sentiment_data, full_part_time_data=full_part_time_data,
                           part_time_sentiment_data=part_time_sentiment_data, evaluationName=evaluationName)

@app.route('/addSubject', methods=["GET", "POST"])
def addSubject():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users where role_id = 2 and school_id = %s and department_id = %s;", (session['school_id'], session['department_id']))
    teachers = cur.fetchall()

    cur.close()

    if request.method == "POST":
        title = request.form.get('title')
        edpCode = request.form.get('edpcode')
        instructor_id = request.form.get('teacher')
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM subjects where edpcode = %s", (edpCode,))
        existing = cur.fetchone()
        if existing:
            flash('Subject already existing!', 'danger')
            return redirect(url_for('addSubject'))

        cur.execute("INSERT INTO subjects(edpcode, title, teacherId) VALUES (%s, %s, %s)",
                    (edpCode, title, instructor_id))

        mysql.connection.commit()
        flash('Successfully added subject ' + title + '!','success')
        return redirect(url_for('addSubject'))

    else:
        return render_template('addSubject.html', teachers=teachers)


@app.route('/editSubject/<subjectid>', methods=["GET", "POST"])
def editSubject(subjectid):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE role_id = 2 and school_id = %s and department_id = %s",
                (session['school_id'], session['department_id']))
    teachers_id = cur.fetchall()

    if len(teachers_id) == 0:
        teachers_id = [0, 0]
        teachers_id = tuple(teachers_id)

    cur.execute("SELECT * FROM users where role_id = 2 and school_id = %s and department_id = %s;", (session['school_id'], session['department_id']))
    teachers = cur.fetchall()
    cur.execute("SELECT * FROM subjects where id = %s and teacherId in %s", (subjectid, teachers_id,))
    subject = cur.fetchone()
    cur.close()
    if not subject:
        flash('Unauthorized access!!', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == "POST":
        title = request.form.get('title')
        edpCode = request.form.get('edpcode')
        instructor_id = request.form.get('teacher')
        cur = mysql.connection.cursor()

        cur.execute("UPDATE subjects set edpcode = %s, title = %s, teacherId = %s WHERE id = %s;",
                    (edpCode, title, instructor_id, subjectid))

        mysql.connection.commit()
        flash('Successfully updated subject ' + title + '!','success')
        return redirect(url_for('subjects'))

    else:
        return render_template('editSubject.html', teachers=teachers, subject=subject)
@app.route("/subjects", methods=["GET"])
def subjects():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))


    cur = mysql.connection.cursor()

    cur.execute("SELECT id FROM users WHERE role_id = 2 and school_id = %s and department_id = %s", (session['school_id'], session['department_id']))
    teachers_id = cur.fetchall()

    if len(teachers_id) == 0:
        teachers_id = [0,0]
        teachers_id = tuple(teachers_id)

    cur.execute('SELECT edpcode, title, users.firstName, users.lastName, subjects.id FROM subjects INNER JOIN users ON users.id = subjects.teacherId WHERE users.id IN %s', (teachers_id,))
    subjects = cur.fetchall()

    cur.execute("SELECT * FROM subjects WHERE teacherId IS NULL;")
    subjects_with_no_teacher = cur.fetchall()

    cur.close()
    return render_template('subjects.html', subjects=subjects, subjects_with_no_teacher=subjects_with_no_teacher)

@app.route('/addTeacher', methods=["GET", "POST"])
def addTeacher():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        idnumber = request.form.get('idnumber')
        firstName = request.form.get('firstname')
        lastName = request.form.get('lastname')
        age = request.form.get('age')
        experience = request.form.get('experience')
        employee_category_id = request.form.get('employeeCategory')
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users where idnumber = %s", (idnumber,))
        existing = cur.fetchone()
        if existing:
            flash('User already existing!', 'danger')
            return redirect(url_for('addTeacher'))

        cur.execute("INSERT INTO users(idnumber, firstname, lastname, password, role_id, school_id, department_id, employeecategory_id, age, yearsExperience) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (idnumber, firstName, lastName, idnumber, 2, session['school_id'], session['department_id'], employee_category_id, age, experience))

        mysql.connection.commit()
        cur.close()
        flash('Successfully added teacher ' + firstName + '! Their default password is their ID number.', 'success')
        return redirect(url_for('addTeacher'))

    else:
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM employeecategory")
        employeeCategory = cur.fetchall()
        return render_template('addTeacher.html', employeeCategory=employeeCategory)
@app.route('/deleteTeacher', methods=["POST"])
def deleteTeacher():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))
    instructor_id = request.form.get('instructorId')

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (instructor_id,))
    mysql.connection.commit()

    flash('Instructor deleted successfully.', 'success')
    return redirect(url_for('teachers'))  # Redirect to an appropriate page
@app.route("/teachers", methods=["GET"])
def teachers():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM users WHERE role_id = 2 and school_id = %s and department_id = %s', (session['school_id'], session['department_id']))
    instructors = cur.fetchall()

    cur.close()
    return render_template('teachers.html', teachers=instructors)

@app.route("/yourSubjects", methods=["GET"])
def yourSubjects():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if session["role_id"] != 2:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    userId = session['userId']

    cur = mysql.connection.cursor()
    cur.execute('SELECT edpcode, title, users.firstName, users.lastName, subjects.id FROM subjects INNER JOIN users ON users.id = subjects.teacherId WHERE teacherId = %s', (userId,))
    subjects = cur.fetchall()


    cur.close()
    return render_template('yourSubjects.html', subjects=subjects)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['xls', 'xlsx']

def allowed_file_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['jpg', 'jpeg', 'png', 'gif']

@app.route("/uploadStudents", methods=["POST"])
def uploadStudents():
    if 'excelFile' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)

    file = request.files['excelFile']
    subjectid = request.form.get('subjectId')
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        try:
            # Process the Excel file directly from memory
            df = pd.read_excel(file)
            # Check for required headers
            required_headers = ['ID Number', 'First Name', 'Last Name']
            if not all(header in df.columns for header in required_headers):
                flash('Invalid file headers. Please make sure the Excel file has the correct headers: ID Number, First Name, Last Name.', 'danger')
                return redirect(url_for('viewStudents', subjectid=subjectid))

            for index, row in df.iterrows():
                idnumber = row['ID Number']
                firstname = row['First Name']
                lastname = row['Last Name']
                cur = mysql.connection.cursor()
                cur.execute(
                    "SELECT * FROM users WHERE idnumber = %s;", (idnumber,))
                existing = cur.fetchone()

                if not existing:
                    cur.execute("INSERT INTO users (idnumber, firstname, lastname, password, role_id, school_id, department_id) VALUES (%s, %s, %s, %s, 1, %s, %s)",
                                (idnumber, firstname, lastname, idnumber, session['school_id'], session['department_id']))
                    studentId = cur.lastrowid
                    cur.execute(
                        "INSERT INTO studentsubjects (student_id, subject_id) VALUES (%s, %s)",
                        (studentId, subjectid))
                else:
                    cur.execute("SELECT * FROM studentsubjects where student_id = %s and subject_id = %s",
                                (existing[0], subjectid))
                    alreadyInSubject = cur.fetchone()
                    if not alreadyInSubject:
                        cur.execute(
                        "INSERT INTO studentsubjects (student_id, subject_id) VALUES (%s, %s)",
                            (existing[0], subjectid))

                mysql.connection.commit()
            flash('Students successfully uploaded and added. Their default password is their ID number (changeable in their profile accounts).', 'success')
        except Exception as e:
            flash(f'Error processing file: {e}', 'danger')
            return redirect(url_for('viewStudents', subjectid=subjectid))

        return redirect(url_for('viewStudents', subjectid=subjectid))
    else:
        flash('Invalid file format. Please upload an Excel file.', 'danger')
        return redirect(url_for('viewStudents', subjectid=subjectid))


@app.route('/viewStudents/<subjectid>', methods=["GET"])
def viewStudents(subjectid):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if session["role_id"] != 2 and session['role_id'] != 3:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))


    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE role_id = 2 and school_id = %s and department_id = %s",
                (session['school_id'], session['department_id']))
    teachers_id = cur.fetchall()

    if len(teachers_id) == 0:
        teachers_id = [0, 0]
        teachers_id = tuple(teachers_id)

    cur.execute('SELECT * FROM subjects where id = %s and teacherId in %s', (subjectid, teachers_id,))
    subject = cur.fetchone()
    if not subject:
        flash('Invalid subject ID!', 'danger')
        return redirect(url_for('dashboard'))

    if session['role_id'] == 2:
        cur.execute('SELECT * FROM subjects where id = %s and teacherid = %s', (subjectid, session['userId']))
        owner = cur.fetchone()
        if not owner:
            flash('Unauthorized access!', 'danger')
            return redirect(url_for('dashboard'))

    subjectName = subject[3]
    cur.execute("SELECT users.idnumber, users.firstName, users.lastName FROM studentsubjects INNER JOIN users ON users.id = studentsubjects.student_id WHERE subject_id = %s", (subjectid,))
    students = cur.fetchall()
    cur.close()
    return render_template('viewStudents.html', students=students, subjectid=subjectid, subjectName=subjectName)


@app.route('/changePassword', methods=['POST'])
def changePassword():
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_new_password = request.form['confirm_new_password']
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users where id = %s", (session['userId'],))
    current_user = cur.fetchone()
    current_password_from_DB = current_user[2]

    if current_password != current_password_from_DB:
        flash('Current password does not match our records.', 'danger')
        return redirect(url_for('profile'))

    # Add your password change logic here
    if new_password == confirm_new_password:
        cur.execute("UPDATE users SET password = %s WHERE id = %s", (new_password, session['userId']))
        mysql.connection.commit()
        flash('Password changed successfully.', 'success')
    else:
        flash('New passwords do not match.', 'danger')

    cur.close()
    return redirect(url_for('profile'))

@app.route('/profile', methods=["GET"])
def profile():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users where id = %s", (session["userId"],))
    userDetails = cur.fetchone()
    roleId = userDetails[5]
    cur.execute("SELECT roleName FROM roles where id = %s", (roleId,))
    roleName = cur.fetchone()
    roleName = roleName[0]
    department_id = userDetails[6]
    cur.execute('SELECT * FROM department WHERE id = %s', (department_id,))
    department = cur.fetchone()
    department_name = department[1]
    return render_template('profile.html', userDetails=userDetails, roleName=roleName, departmentName=department_name)


@app.route('/upload_signature', methods=['POST'])
def upload_signature():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if session['role_id'] != 3:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    if 'signature' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('profile'))

    file = request.files['signature']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('profile'))
    print("file", file)
    if file and allowed_file_image(file.filename):
        # Create the upload folder if it doesn't exist
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        filename = secure_filename(file.filename)

        input_path = io.BytesIO(file.read())
        input_image = Image.open(input_path)
        output_image = remove(input_image)

        # Save the output image as a PNG with transparent background
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], filename.rsplit('.', 1)[0] + '.png')
        output_image.save(output_path)
        # file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        # Update the user details in the database to store the filename
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET esignature = %s WHERE id = %s", (filename.rsplit('.', 1)[0] + '.png', session["userId"]))
        mysql.connection.commit()
        flash('E-signature uploaded successfully!', 'success')
        return redirect(url_for('profile'))
    else:
        flash('Allowed file types are png, jpg, jpeg, gif', 'danger')
        return redirect(url_for('profile'))


@app.route("/addQuestionnaire")
def addQuestionnaire():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM questionnaireset")
    sets = cur.fetchall()
    cur.close()
    return render_template('addQuestionnaire.html', sets=sets)


@app.route("/createQuestionnaire", methods=["POST"])
def createQuestionnaire():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if session["role_id"] != 3:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    # Get template information
    template_name = request.form.get('templateName')
    template_description = request.form.get('description')
    modality = request.form.get('modality')
    # Initialize a variable to keep track of the total percentage
    total_percentage = 0
    sections = []

    # Iterate over each section
    for section_num in range(1, 6):
        section_name = request.form.get(f'section{section_num}Name')
        section_description = request.form.get(f'section{section_num}Description')
        section_percentage = request.form.get(f'section{section_num}Percentage')

        # Check if section_percentage is a number
        if not section_percentage.isdigit():
            flash(f'Section {section_num} percentage must be a number.', 'danger')
            session['form_data'] = request.form.to_dict()
            return redirect(url_for('addQuestionnaire'))

        section_percentage = int(section_percentage)

        # Add to total_percentage
        total_percentage += section_percentage

        # Store section details
        sections.append({
            'number': section_num,
            'name': section_name,
            'description': section_description,
            'percentage': section_percentage,
        })

    # Check if total_percentage is 100
    if total_percentage != 100:
        flash('Total percentage of all sections must equal 100.', 'danger')
        session['form_data'] = request.form.to_dict()
        return redirect(url_for('addQuestionnaire'))

    # Insert into questionnaireset table
    cur.execute("INSERT INTO questionnaireset (name, description, school_id, department_id, modality) VALUES (%s, %s, %s, %s, %s)",
                (template_name, template_description, session['school_id'], session['department_id'], modality))
    questionnaireset_id = cur.lastrowid

    # Iterate over each section and insert into the database
    for section in sections:
        cur.execute("INSERT INTO section (section, name, description, percentage, questionnaireset_id) VALUES (%s, %s, %s, %s, %s)",
                    (section['number'], section['name'], section['description'], section['percentage'], questionnaireset_id))
        section_id = cur.lastrowid

        # Dynamically find all questions for the current section
        question_num = 1
        has_questions = False
        while True:
            question_text = request.form.get(f'section{section["number"]}Question{question_num}')
            if not question_text:
                break  # Exit the loop if no more questions are found
            has_questions = True
            # Insert into questionaire table
            cur.execute("INSERT INTO questionaire (section, question, questionnaireset_id) VALUES (%s, %s, %s)",
                        (section['number'], question_text, questionnaireset_id))
            question_num += 1

        # Check if the section has at least one question
        if not has_questions:
            flash(f'Section {section["number"]} must have at least one question.', 'danger')
            cur.execute("DELETE FROM section WHERE id = %s", (section_id,))
            cur.execute("DELETE FROM questionnaireset WHERE id = %s", (questionnaireset_id,))
            session['form_data'] = request.form.to_dict()
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('addQuestionnaire'))

    # Commit the transaction
    mysql.connection.commit()
    cur.close()
    flash('You successfully made a new questionnaire', 'success')
    return redirect(url_for('dashboard'))


@app.route("/downloadTemplateStudents")
def downloadTemplateStudents():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')

    # Create a DataFrame with the template structure
    df = pd.DataFrame(columns=['ID Number', 'First Name', 'Last Name'])

    # Write the DataFrame to the Excel file
    df.to_excel(writer, index=False, sheet_name='Template')

    # Save the Excel file to the BytesIO buffer
    writer.close()
    output.seek(0)

    # Return the response directly using Response
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment;filename=students_template.xlsx'
        }
    )

@app.route("/downloadTemplate")
def downloadTemplate():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')

    for section_num in range(1, 6):
        questions_count = [5, 5, 5, 5, 5][section_num - 1]
        data = {'Section Name': [""], 'Section Description': [""], 'Section Percentage': [0]}
        for question_num in range(1, questions_count + 1):
            data[f'Question {question_num}'] = [""]
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name=f'Section {section_num}', index=False)

    writer.close()
    output.seek(0)

    return Response(output,
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment;filename=evaluation_template.xlsx"})
@app.route("/uploadQuestionnaire", methods=["POST"])
def uploadQuestionnaire():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if session["role_id"] != 3:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['file']
    if file:
        df_dict = pd.read_excel(file, sheet_name=None)
        cur = mysql.connection.cursor()

        template_name = request.form.get('templateNameDownload')
        description = request.form.get('descriptionDownload')
        modality = request.form.get('modality')
        cur.execute("INSERT INTO questionnaireset (name, description, school_id, department_id, modality) VALUES (%s, %s, %s, %s, %s)", (template_name, description, session['school_id'], session['department_id'], modality))
        questionnaireset_id = cur.lastrowid

        # For trapping
        total_percentage = 0
        error = False

        for section_num, (sheet_name, df) in enumerate(df_dict.items(), start=1):
            section_name = df.iloc[0]['Section Name']
            section_description = df.iloc[0]['Section Description']
            section_percentage = df.iloc[0]['Section Percentage']

            if isinstance(section_name, float) and pd.isna(section_name):
                section_name = None
            if isinstance(section_description, float) and pd.isna(section_description):
                section_description = None

            # Check for blank fields
            if not all([section_name, section_description]):
                error = True
                flash('Section name and description are required.', 'danger')
                break

            if isinstance(section_percentage, float) and pd.isna(section_percentage):
                error = True
                flash('Section percentage must be a valid number.', 'danger')
                break

            try:
                section_percentage = int(section_percentage)
                total_percentage += section_percentage
            except ValueError:
                error = True
                flash('Section percentage must be a number.', 'danger')
                break

            # Dynamically determine the number of questions
            questions = [col for col in df.columns if col.startswith('Question')]
            for question in questions:
                question_text = df.iloc[0][question]
                if isinstance(question_text, float) and pd.isna(question_text):
                    question_text = None
                if not question_text:
                    error = True
                    flash(f'{question} in section {section_num} is required.', 'danger')
                    break

        # Check if total percentage is not 100
        if total_percentage != 100:
            error = True
            flash('Total section percentage must be 100.', 'danger')

        if error:
            return redirect(url_for('addQuestionnaire'))  # Redirect to the form page

        for section_num, (sheet_name, df) in enumerate(df_dict.items(), start=1):
            section_name = df.iloc[0]['Section Name']
            section_description = df.iloc[0]['Section Description']
            section_percentage = df.iloc[0]['Section Percentage']
            cur.execute("INSERT INTO section (section, name, description, percentage, questionnaireset_id) VALUES (%s, %s, %s, %s, %s)",
                        (section_num, section_name, section_description, section_percentage, questionnaireset_id))
            section_id = cur.lastrowid

            # Dynamically insert questions
            questions = [col for col in df.columns if col.startswith('Question')]
            for question in questions:
                question_text = df.iloc[0][question]
                cur.execute("INSERT INTO questionaire (section, question, questionnaireset_id) VALUES (%s, %s, %s)",
                            (section_num, question_text, questionnaireset_id))

        mysql.connection.commit()
        cur.close()
    flash('You successfully made a new questionnaire', 'success')

    return redirect(url_for('dashboard'))


@app.route("/newRating", methods=["GET"])
def newRating():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        return redirect(url_for('dashboard'))

    return render_template('addRating.html')

def is_valid_range(range_value):
    pattern = r'^\d+(\.\d+)?-\d+(\.\d+)?$'
    return re.match(pattern, range_value)

@app.route("/createRating", methods=["POST"])
def createRating():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    title = request.form['title']
    description1 = request.form['rating1']
    range1 = request.form['range1']
    description2 = request.form['rating2']
    range2 = request.form['range2']
    description3 = request.form['rating3']
    range3 = request.form['range3']
    description4 = request.form['rating4']
    range4 = request.form['range4']
    description5 = request.form['rating5']
    range5 = request.form['range5']

    if not (is_valid_range(range1) and is_valid_range(range2) and is_valid_range(range3) and is_valid_range(
            range4) and is_valid_range(range5)):
        flash('One or more range values are not in the correct format (e.g., "1-1.90").', 'danger')
        return redirect(url_for('newRating'))
    # Open a cursor to perform database operations
    cur = mysql.connection.cursor()
    # Execute the query
    cur.execute("INSERT INTO rating (title, range1, description1, range2, description2, range3, description3, range4, description4, range5, description5, school_id, department_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (title, range1, description1, range2, description2, range3, description3, range4, description4, range5, description5, session['school_id'], session['department_id']))
    # Commit to the database
    mysql.connection.commit()
    # Close the cursor
    cur.close()
    flash('Successfully created a new rating system', 'success')
    return redirect('dashboard')

@app.route("/addEvaluation")
def addEvaluation():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM questionnaireset WHERE school_id = %s and department_id = %s", (session['school_id'], session['department_id']))
    sets = cur.fetchall()
    cur.execute("SELECT * FROM semester")
    semesters = cur.fetchall()
    cur.execute("SELECT * FROM schoolYear")
    years = cur.fetchall()
    cur.execute("SELECT * FROM rating WHERE school_id = %s and department_id = %s", (session['school_id'], session['department_id']))
    ratings = cur.fetchall()
    cur.close()
    return render_template('addEvaluationForm.html',ratings=ratings, sets=sets, semesters=semesters, years=years)

@app.route("/editEvaluation/<evaluationFormId>", methods=["GET", "POST"])
def editEvaluation(evaluationFormId):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))


    cur = mysql.connection.cursor()
    cur.execute('SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s', (session['school_id'], session['department_id']))
    questionnaireset_ids = cur.fetchall()
    if len(questionnaireset_ids) == 0:
        questionnaireset_ids = [0,0]
        questionnaireset_ids = tuple(questionnaireset_ids)

    cur.execute("SELECT * FROM evaluationForms WHERE id = %s and questionnaireset_id in %s", (evaluationFormId, questionnaireset_ids))
    evaluationForm = cur.fetchone()
    if not evaluationForm:
        flash('Invalid evaluation form ID', 'danger')
        return redirect(url_for('dashboard'))
    cur.execute("SELECT * FROM questionnaireset WHERE school_id = %s and department_id = %s", (session['school_id'], session['department_id']))
    sets = cur.fetchall()
    cur.execute("SELECT * FROM semester")
    semesters = cur.fetchall()
    cur.execute("SELECT * FROM schoolYear")
    years = cur.fetchall()
    cur.execute("SELECT * FROM rating WHERE school_id = %s and department_id = %s", (session['school_id'], session['department_id']))
    ratings = cur.fetchall()

    cur.close()

    if request.method == "POST":
        cur = mysql.connection.cursor()
        title = request.form.get('title')
        date_start = request.form.get('dateStart')
        date_end = request.form.get('dateEnd')
        questionnaireset_id = request.form.get('set')
        semester_id = request.form.get('semester')
        schoolyear_id = request.form.get('schoolYear')
        rating_id = request.form.get('rating')

        # today = date.today()
        # if datetime.strptime(date_end, '%Y-%m-%d').date() < today:
        #     flash('End date cannot be less than today.', 'danger')
        #     return redirect(url_for('editEvaluation', evaluationFormId=evaluationFormId))

        cur.execute("""
        UPDATE evaluationForms SET title = %s, dateStart = %s, dateEnd = %s, questionnaireset_id = %s,
        semester_id = %s, schoolyear_id = %s, rating_id = %s WHERE id = %s    
        """, (title, date_start, date_end, questionnaireset_id, semester_id, schoolyear_id, rating_id, evaluationFormId ))

        mysql.connection.commit()
        cur.close()

        flash('Successfully edited the evaluation form ' + str(evaluationForm[1]), 'success')
        return redirect(url_for('dashboard'))
    else:
        return render_template("editEvaluation.html", sets=sets, evaluationForm=evaluationForm, ratings=ratings, years=years, semesters=semesters)


@app.route("/createEvaluationForm", methods=["POST"])
def createEvaluationForm():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    # Get form data
    title = request.form.get('title')
    date_start = request.form.get('dateStart')
    date_end = request.form.get('dateEnd')
    questionnaireset_id = request.form.get('set')
    semester_id = request.form.get('semester')
    schoolyear_id = request.form.get('schoolYear')
    rating_id = request.form.get('rating')

    # Check if end date is less than today
    today = date.today()
    if datetime.strptime(date_end, '%Y-%m-%d').date() < today:
        flash('End date cannot be less than today.', 'danger')
        return redirect(url_for('addEvaluation'))

    # Insert into evaluationForms table
    cur.execute("""
        INSERT INTO evaluationForms (title, dateStart, dateEnd, questionnaireset_id, semester_id, schoolyear_id, rating_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (title, date_start, date_end, questionnaireset_id, semester_id, schoolyear_id, rating_id))

    # Commit the trandsaction
    mysql.connection.commit()
    cur.close()
    flash('You successfully made a new evaluation form', 'success')
    return redirect(url_for('dashboard'))


@app.route("/viewEvaluation/<evaluationFormId>/<subject>/<respondents>")
def viewEvaluation(evaluationFormId, subject, respondents):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 2):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s",
                (session['school_id'], session['department_id']))
    questionnairesets = cur.fetchall()
    if len(questionnairesets) == 0:
        questionnairesets = [0, 0]
    questionnairesets = tuple(questionnairesets)

    sql = "SELECT * FROM evaluationForms WHERE id = %s and questionnaireset_id IN %s"
    val = (evaluationFormId, questionnairesets,)
    cur.execute(sql, val)
    evaluation_forms = cur.fetchone()
    if not evaluation_forms:
        # Redirect the user back to the dashboard if there are no evaluation forms
        flash("Evaluation form invalid", "danger")
        return redirect(url_for('dashboard'))

    questionnaireSet_id = evaluation_forms[4]
    if questionnaireSet_id is None:
        if session['role_id'] == 3:
            flash('The selected questionnaire template has been deleted. Edit your evaluation.', 'danger')
            return redirect(url_for('editEvaluation', evaluationFormId=evaluationFormId))

    ratingId = evaluation_forms[7]
    if ratingId is None:
        if session['role_id'] == 3:
            flash('The selected rating has been deleted. Edit your evaluation.', 'danger')
            return redirect(url_for('editEvaluation', evaluationFormId=evaluationFormId))

    evaluationTitle = evaluation_forms[1]
    semesterId = evaluation_forms[5]
    sql = "SELECT * FROM semester WHERE id = %s"
    val = (semesterId,)
    cur.execute(sql, val)
    semester = cur.fetchone()

    schoolyearid = evaluation_forms[6]
    cur = mysql.connection.cursor()
    sql = "SELECT * FROM schoolyear WHERE id = %s"
    val = (schoolyearid,)
    cur.execute(sql, val)
    schoolyear = cur.fetchone()

    cur.execute("SELECT subjects.id, subjects.edpCode, subjects.title FROM subjects WHERE teacherId = %s", (session["userId"],))
    subjects = cur.fetchall()

    ratingId = evaluation_forms[7]
    sql = "SELECT * FROM rating WHERE id = %s"
    val = (ratingId,)
    cur.execute(sql, val)
    rating = cur.fetchone()
    range5Array = [float(x) for x in rating[10].split('-')]
    range4Array = [float(x) for x in rating[8].split('-')]
    range3Array = [float(x) for x in rating[6].split('-')]
    range2Array = [float(x) for x in rating[4].split('-')]
    range1Array = [float(x) for x in rating[2].split('-')]

    # print(range5Array)
    # common queries
    sql = "SELECT * FROM questionaire where section = 1 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section1 = cur.fetchall()

    sql = "SELECT * FROM questionaire where section = 2 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section2 = cur.fetchall()

    sql = "SELECT * FROM questionaire where section = 3 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section3 = cur.fetchall()

    sql = "SELECT * FROM questionaire where section = 4 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section4 = cur.fetchall()

    sql = "SELECT * FROM questionaire where section = 5 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section5 = cur.fetchall()

    # <!-- DB guide-> https://imgur.com/YMKA4ib -->
    cur.execute("""SELECT DISTINCT section.id, section.section, section.name, section.description, section.percentage, 
    				(select count(question) from questionaire  where section = '1' AND questionnaireset_id = '1') as total1, 
    				(select count(question) from questionaire  where section = '2' AND questionnaireset_id = '1') as total2, 
    				(select count(question) from questionaire  where section = '3' AND questionnaireset_id = '1') as total3, 
    				(select count(question) from questionaire  where section = '4' AND questionnaireset_id = '1') as total4,
    				(select count(question) from questionaire  where section = '5' AND questionnaireset_id = '1') as total5 
    				from section 
    				right join questionaire on section.section = questionaire.section WHERE section.questionnaireset_id = %s""",
                (questionnaireSet_id,))
    sectionsleft = cur.fetchall()
    print("Length sections left: ", str(len(sectionsleft)))
    cur.execute(""" SELECT questionaire.section, questionaire.question from questionaire
    					WHERE questionaire.questionnaireset_id = %s """, (questionnaireSet_id,))
    sectionsright = cur.fetchall()
    # End for common queries

    # cur.execute("SELECT employeecategory_id FROM users WHERE id = %s", (session["userId"],))
    # category = cur.fetchone()
    category = "all"
    # print(category)
    comments = getSentimentValuesFaculty(session["userId"], subject, evaluationFormId, category, respondents)

    print(subject)
    # get total number of respondents
    numofrespondents = getNumberOfRespondentsFaculty(session["userId"], subject, evaluationFormId, category, respondents)

    # get rating records from all sections
    evalsecans = getRatingValuesFaculty(session["userId"], subject, evaluationFormId, category, respondents)


    return render_template('viewEvaluation.html', evaluationTitle=evaluationTitle,
                           section1=section1, section2=section2,
                           lensec1=len(section1), lensec2=len(section2),
                           section3=section3, lensec3=len(section3),
                           section4=section4, lensec4=len(section4),
                           section5=section5, lensec5=len(section5),
                           datacomments=comments,
                           countrespondents=numofrespondents,
                           sectionsleft=sectionsleft,
                           sectionsright=sectionsright,
                           lensectionsleft=len(sectionsleft),
                           lensectionsright=len(sectionsright),
                           evalsecans=evalsecans,
                           teachers=teachers,
                           subjects=subjects, rating=rating,
                           range5Array = range5Array, range4Array = range4Array, range3Array = range3Array, range2Array = range2Array, range1Array = range1Array,
                           semester=semester, schoolyear=schoolyear)

@app.route("/teachersevaluation/<teacher>/<subject>/<evaluationFormId>/<category>", methods=["POST", "GET"])
def evaluate(teacher, subject, evaluationFormId, category): #summary
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if(session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    global G_TEACHER_NAME
    global G_SUBJECT_NAME
    global G_NUMBER_OF_RESPONDENTS
    global G_TEACHER_ID
    global G_SUBJECT_ID
    global G_EVALUATION_FORM_ID
    global G_CATEGORY_NAME

    G_TEACHER_ID = teacher
    G_SUBJECT_ID = subject
    G_EVALUATION_FORM_ID = evaluationFormId
    G_TEACHER_NAME = getSelectedTeacherName(teacher)
    G_SUBJECT_NAME = getSelectedSubjectTitle(teacher, subject)
    G_NUMBER_OF_RESPONDENTS = getNumberOfRespondents(teacher, subject, evaluationFormId, category)
    G_CATEGORY_NAME = category

    print(G_TEACHER_ID)

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s",
                (session['school_id'], session['department_id']))
    questionnairesets = cur.fetchall()
    if len(questionnairesets) == 0:
        questionnairesets = [0, 0]
    questionnairesets = tuple(questionnairesets)

    sql = "SELECT * FROM evaluationForms WHERE id = %s and questionnaireset_id IN %s"
    val = (evaluationFormId,questionnairesets,)
    cur.execute(sql, val)
    evaluation_forms = cur.fetchone()

    if not evaluation_forms:
        # Redirect the user back to the dashboard if there are no evaluation forms
        flash("Evaluation form invalid", "danger")
        return redirect(url_for('dashboard'))

    questionnaireSet_id = evaluation_forms[4]
    if questionnaireSet_id is None:
        if session['role_id'] == 3:
            flash('The selected questionnaire template has been deleted. Edit your evaluation.', 'danger')
            return redirect(url_for('editEvaluation', evaluationFormId=evaluationFormId))



    ratingId = evaluation_forms[7]
    if ratingId is None:
        if session['role_id'] == 3:
            flash('The selected rating has been deleted. Edit your evaluation.', 'danger')
            return redirect(url_for('editEvaluation', evaluationFormId=evaluationFormId))

    evaluationTitle = evaluation_forms[1]
    semesterId = evaluation_forms[5]
    cur = mysql.connection.cursor()
    sql = "SELECT * FROM semester WHERE id = %s"
    val = (semesterId,)
    cur.execute(sql, val)
    semester = cur.fetchone()

    schoolyearid = evaluation_forms[6]
    cur = mysql.connection.cursor()
    sql = "SELECT * FROM schoolyear WHERE id = %s"
    val = (schoolyearid,)
    cur.execute(sql, val)
    schoolyear = cur.fetchone()

    ratingId = evaluation_forms[7]
    sql = "SELECT * FROM rating WHERE id = %s"
    val = (ratingId,)
    cur.execute(sql, val)
    rating = cur.fetchone()
    range5Array = [float(x) for x in rating[10].split('-')]
    range4Array = [float(x) for x in rating[8].split('-')]
    range3Array = [float(x) for x in rating[6].split('-')]
    range2Array = [float(x) for x in rating[4].split('-')]
    range1Array = [float(x) for x in rating[2].split('-')]

    # print(range5Array)
    # common queries
    sql = "SELECT * FROM questionaire where section = 1 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section1 = cur.fetchall()

    sql = "SELECT * FROM questionaire where section = 2 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section2 = cur.fetchall()

    sql = "SELECT * FROM questionaire where section = 3 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section3 = cur.fetchall()

    sql = "SELECT * FROM questionaire where section = 4 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section4 = cur.fetchall()

    sql = "SELECT * FROM questionaire where section = 5 and questionnaireset_id = %s"
    val = (questionnaireSet_id,)
    cur.execute(sql, val)
    section5 = cur.fetchall()

    # <!-- DB guide-> https://imgur.com/YMKA4ib -->
    cur.execute("""SELECT DISTINCT section.id, section.section, section.name, section.description, section.percentage, 
				(select count(question) from questionaire  where section = '1' AND questionnaireset_id = '1') as total1, 
				(select count(question) from questionaire  where section = '2' AND questionnaireset_id = '1') as total2, 
				(select count(question) from questionaire  where section = '3' AND questionnaireset_id = '1') as total3, 
				(select count(question) from questionaire  where section = '4' AND questionnaireset_id = '1') as total4,
				(select count(question) from questionaire  where section = '5' AND questionnaireset_id = '1') as total5 
				from section 
				right join questionaire on section.section = questionaire.section WHERE section.questionnaireset_id = %s""", (questionnaireSet_id,))
    sectionsleft = cur.fetchall()
    print("Length sections left: ", str(len(sectionsleft)))
    cur.execute(""" SELECT questionaire.section, questionaire.question from questionaire
					WHERE questionaire.questionnaireset_id = %s """, (questionnaireSet_id,))
    sectionsright = cur.fetchall()
    # End for common queries

    # FOR DEFAULT QUERIES
    # queries for the teachers and subject filter
    sql = "SELECT * FROM users WHERE role_id = 2 and school_id = %s and department_id = %s order by (case idnumber when %s then 0 else 1 end), lastName asc"
    val = (session['school_id'], session['department_id'], teacher)
    cur.execute(sql, val)
    teachers = cur.fetchall()
    # print('teachers')
    # print(teachers)
    subjects = []
    if category != 'all':
        sql = "SELECT * FROM users WHERE role_id = 2 and school_id = %s and department_id = %s and employeecategory_id = %s order by (case idnumber when %s then 0 else 1 end), lastName asc"
        val = (session['school_id'], session['department_id'], category, teacher)
        cur.execute(sql, val)
        teachers = cur.fetchall()
    else:
        if teacher == "all":
            if subject == "all":
                subjects = []
        else:
            sql = "SELECT DISTINCT subjects.id, subjects.edpCode, subjects.title FROM subjects INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE teachers.id = %s"
            val = (teacher,)
            cur.execute(sql, val)
            subjects = cur.fetchall()
            print('subjects', subjects)
            # subjects = cur.fetchall()
            # sql = "SELECT * FROM subjects WHERE teacherId = %s or edpCode = 0 order by (case edpCode when %s then 0 else 1 end), title asc"
            # val = (teachers[0][0], subject,)
            # cur.execute(sql, val)

    cur.execute("SELECT * FROM employeecategory")
    employeeCategory = cur.fetchall()

    # if (subject != "all" and (teacher != "0")):
    #     sql = "SELECT subjects.id, subjects.edpCode, subjects.title FROM studentsubjects INNER JOIN users AS students ON studentsubjects.student_id = students.id INNER JOIN subjects ON studentsubjects.subject_id = subjects.id INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE teachers.id = %s AND subjects.id = %s"
    #     # val = (subject,)
    #     cur.execute(sql, val)
    #     # subjects = cur.fetchall()
    #     # sql = "SELECT * FROM subjects WHERE teacherId = %s or edpCode = 0 order by (case edpCode when %s then 0 else 1 end), title asc"
    #     val = (teachers[0][0], subject,)
    #     # cur.execute(sql, val)
    #     subjects = cur.fetchall()
    # else:
    #     sql = "SELECT subjects.id, subjects.edpCode, subjects.title FROM studentsubjects INNER JOIN users AS students ON studentsubjects.student_id = students.id INNER JOIN subjects ON studentsubjects.subject_id = subjects.id INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE teachers.id = %s AND subjects.id = %s"
    #     # val = (subject,)
    #     cur.execute(sql, val)
    #     # subjects = cur.fetchall()
    #     # sql = "SELECT * FROM subjects WHERE teacherId = %s or edpCode = 0 order by (case edpCode when %s then 0 else 1 end), title asc"
    #     val = (teachers[0][0], subject,)
    #     # cur.execute(sql, val)
    #     subjects = cur.fetchall()
    #     # sql = "SELECT * FROM subjects order by (case edpCode when %s then 0 else 1 end), title asc"
    #     # val = (subject,)
    #     # cur.execute(sql, val)
    #     # subjects = cur.fetchall()
    # end for default queries

    # get sentiment values
    comments = getSentimentValues(teacher, subject, evaluationFormId, category)

    # get total number of respondents
    numofrespondents = getNumberOfRespondents(teacher, subject, evaluationFormId, category)

    # get rating records from all sections
    evalsecans = getRatingValues(teacher, subject, evaluationFormId, category)

    print('evalsecans')
    # print(evalsecans[0])
    # END FOR FILTER RECORDS
    cur.close()

    return render_template("teachers_evaluation.html", evaluationTitle=evaluationTitle,
                           section1=section1, section2=section2,
                           lensec1=len(section1), lensec2=len(section2),
                           section3=section3, lensec3=len(section3),
                           section4=section4, lensec4=len(section4),
                           section5=section5, lensec5=len(section5),
                           datacomments=comments,
                           countrespondents=numofrespondents, employeeCategory=employeeCategory,
                           sectionsleft=sectionsleft,
                           sectionsright=sectionsright,
                           lensectionsleft=len(sectionsleft),
                           lensectionsright=len(sectionsright),
                           evalsecans=evalsecans,
                           teachers=teachers,
                           subjects=subjects,
                           isDefault=isDefaultUrlForSummary(teacher, subject), rating=rating,
                           range5Array = range5Array, range4Array = range4Array, range3Array = range3Array, range2Array = range2Array, range1Array = range1Array,
                           semester=semester, schoolyear=schoolyear
                           )


@app.route("/evaluation/<teacher>/<subject>/<evaluationFormId>", methods=["POST", "GET"])
def evaluation(teacher, subject, evaluationFormId):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    subject_id = subject
    userId = session['userId']
    roleId = session['role_id']
    if roleId == 2:
        flash("Unauthorized access!", "warning")
        return redirect(url_for('dashboard'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s",
                (session['school_id'], session['department_id']))
    questionnairesets = cur.fetchall()
    if len(questionnairesets) == 0:
        questionnairesets = [0, 0]
    questionnairesets = tuple(questionnairesets)

    sql = "SELECT * FROM evaluationForms WHERE dateEnd >= CURDATE() and id = %s and questionnaireset_id IN %s"
    val = (evaluationFormId,questionnairesets,)
    cur.execute(sql, val)
    evaluation_forms = cur.fetchone()

    #trappings
    if not evaluation_forms:
        # Redirect the user back to the dashboard if there are no evaluation forms
        flash("Evaluation form invalid", "danger")
        return redirect(url_for('dashboard'))

    questionnaireset_id = evaluation_forms[4]
    ratingId = evaluation_forms[7]
    if ratingId is None:
        if roleId == 3:
            flash('The selected rating has been deleted. Edit your evaluation.', 'danger')
            return redirect(url_for('editEvaluation', evaluationFormId=evaluationFormId))
        else:
            flash('The selected rating has been deleted. Wait for the dean to fix it.', 'danger')
            return redirect(url_for('dashboard'))
    if questionnaireset_id is None:
        if roleId == 3:
            flash('The selected questionnaire template has been deleted. Edit your evaluation.', 'danger')
            return redirect(url_for('editEvaluation', evaluationFormId=evaluationFormId))
        else:
            flash('The selected questionnaire template has been deleted. Wait for the dean to fix it.', 'danger')
            return redirect(url_for('dashboard'))
    # cur.execute('SELECT * FROM evaluation WHERE evaluationForm_id = %s', (evaluationFormId,))
    # evaluated = cur.fetchall()

    if roleId == 1:
        sql = "SELECT * FROM evaluationForms WHERE id = %s and dateEnd > CURDATE() and questionnaireset_id IN %s"
        val = (evaluationFormId, questionnairesets,)
        cur.execute(sql, val)
        evaluationWithDate = cur.fetchone()
        if not evaluationWithDate:
            # Redirect the user back to the dashboard if there are no evaluation forms
            flash("Evaluation form invalid", "danger")
            return redirect(url_for('dashboard'))

        cur.execute("SELECT * FROM studentsubjects WHERE student_id = %s", (userId,))
        studentSubjects = cur.fetchall()
        takenAll = True
        for subject in studentSubjects:
            cur.execute("SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
            (evaluation_forms[0], userId, subject[2]))
            res = cur.fetchone()
            if res is None:
                takenAll = False
                break
        if takenAll:
            flash('You have completed this evaluation already!', 'danger')
            return redirect(url_for('dashboard'))

    cur.execute("SELECT * FROM section WHERE questionnaireset_id = %s", (questionnaireset_id,))
    section_details = cur.fetchall()
    if roleId == 1:
        cur.execute("SELECT * FROM studentsubjects WHERE student_id = %s", (userId,))
        studentSubjects = cur.fetchall()
        takenAll = True

        for subject in studentSubjects:
            cur.execute("SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
                        (evaluationFormId, userId, subject[2]))
            res = cur.fetchone()
            print(res)
            if res is None:
                takenAll = False
                break
        if takenAll:
            flash('You have evaluated all teachers!', 'success')
            return redirect(url_for('dashboard'))

    if roleId == 2 or roleId == 3:
        cur.execute("SELECT id FROM users WHERE role_id = 2 and school_id = %s and department_id = %s", (session['school_id'], session['department_id']))
        teachers_id = cur.fetchall()
        if len(teachers_id) == 0:
            teachers_id = [0, 0]
            teachers_id = tuple(teachers_id)

        cur.execute("SELECT * FROM subjects WHERE teacherId in %s", (teachers_id,))
        subjects = cur.fetchall()
        takenAll = True

        for subject in subjects:
            cur.execute("SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
                        (evaluationFormId, userId, subject[0]))
            res = cur.fetchone()
            if res is None:
                takenAll = False
                break
        if takenAll:
            flash('You have evaluated all teachers!', 'success')
            return redirect(url_for('dashboard'))

    ratingId = evaluation_forms[7]

    sql = "SELECT * FROM rating WHERE id = %s"
    val = (ratingId,)
    cur.execute(sql, val)
    rating = cur.fetchone()

    cur.execute("SELECT * FROM questionaire where section = 1 and questionnaireset_id = %s", (questionnaireset_id,))
    section1 = cur.fetchall()
    cur.execute("SELECT * FROM questionaire where section = 2 and questionnaireset_id = %s", (questionnaireset_id,))
    section2 = cur.fetchall()
    cur.execute("SELECT * FROM questionaire where section = 3 and questionnaireset_id = %s", (questionnaireset_id,))
    section3 = cur.fetchall()
    cur.execute("SELECT * FROM questionaire where section = 4 and questionnaireset_id = %s", (questionnaireset_id,))
    section4 = cur.fetchall()
    cur.execute("SELECT * FROM questionaire where section = 5 and questionnaireset_id = %s", (questionnaireset_id,))
    section5 = cur.fetchall()

    # FOR DEFAULT QUERIES
    # queries for the teachers and subject filter
    sql = "SELECT DISTINCT teachers.id, teachers.firstName AS teacherFirstName, teachers.lastName AS teacherLastName FROM studentsubjects INNER JOIN users AS students ON studentsubjects.student_id = students.id INNER JOIN subjects ON studentsubjects.subject_id = subjects.id INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE students.id = %s;"
    val = (session['userId'],)
    cur.execute(sql, val)
    teachers = cur.fetchall()
    print(teachers)
    subjects = []
    cur.execute("SELECT subject_id from evaluation WHERE evaluationform_id = %s and idstudent = %s", (evaluationFormId, userId,))
    excluded_subjects = cur.fetchall()
    print(len(excluded_subjects))
    # if len(excluded_subjects) == 0:
    #     excluded_subjects = (0,)
    excluded_subjects = tuple(item[0] for item in excluded_subjects)

    # Handle case where there are no excluded subjects
    if not excluded_subjects:
        excluded_subjects = (0,0)

    # excluded_subjects = tuple(excluded_subjects)
    print('excluded subs')
    print(type(excluded_subjects))
    if session['role_id'] == 3 or session['role_id'] == 2:
        cur.execute("SELECT id FROM users WHERE role_id = 2 and school_id = %s and department_id = %s",
                    (session['school_id'], session['department_id']))
        teachers_id = cur.fetchall()
        if len(teachers_id) == 0:
            teachers_id = [0, 0]
            teachers_id = tuple(teachers_id)
        sql = "SELECT DISTINCT teachers.id, teachers.firstName AS teacherFirstName, teachers.lastName AS teacherLastName FROM studentsubjects INNER JOIN users AS students ON studentsubjects.student_id = students.id INNER JOIN subjects ON studentsubjects.subject_id = subjects.id INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE teachers.id IN %s;"
        val = (teachers_id,)
        cur.execute(sql, val)
        teachers = cur.fetchall()
        if (teacher == "all"):
            sql = "SELECT DISTINCT teachers.id, teachers.firstName AS teacherFirstName, teachers.lastName AS teacherLastName FROM subjects INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE subjects.teacherId in %s;"
            val = (teachers_id,)
            cur.execute(sql, val)
            teachers = cur.fetchall()
            # print(teachers)
            subjects = []
        else:
            sql = "SELECT * FROM users WHERE id = %s and role_id = 2"
            cur.execute(sql, (teacher,))
            teacher_exist = cur.fetchone()
            if not teacher_exist:
                flash('Teacher ID is invalid', 'danger')
                return redirect(url_for('dashboard'))

            if (subject_id == "all"):
                sql = "SELECT DISTINCT teachers.id, teachers.firstName AS teacherFirstName, teachers.lastName AS teacherLastName FROM subjects INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE teachers.id IN %s;"
                cur.execute(sql, (teachers_id,))
                teachers = cur.fetchall()
                # sql = "SELECT teachers.id, teachers.firstName AS teacherFirstName, teachers.lastName AS teacherLastName FROM studentsubjects INNER JOIN users AS students ON studentsubjects.student_id = students.id INNER JOIN subjects ON studentsubjects.subject_id = subjects.id INNER JOIN users AS teachers ON subjects.teacherid = teachers.id;"
                sql = "SELECT DISTINCT subjects.id, subjects.edpCode, subjects.title FROM subjects INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE subjects.teacherid = %s and subjects.id NOT IN %s"
                val = (teacher, excluded_subjects,)
                cur.execute(sql, val)
                subjects = cur.fetchall()
            else:
                sql = "SELECT DISTINCT teachers.id, teachers.firstName AS teacherFirstName, teachers.lastName AS teacherLastName FROM users AS teachers WHERE teachers.id IN %s;"
                cur.execute(sql, (teachers_id,))
                teachers = cur.fetchall()
                sql = "SELECT DISTINCT subjects.id, subjects.edpCode, subjects.title FROM subjects INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE teachers.id  = %s and subjects.id NOT IN %s"
                val = (teacher, excluded_subjects,)
                cur.execute(sql, val)
                subjects = cur.fetchall()
    else:
        if(teacher == "all"):
            # sql = "SELECT teachers.id, teachers.firstName AS teacherFirstName, teachers.lastName AS teacherLastName FROM studentsubjects INNER JOIN users AS students ON studentsubjects.student_id = students.id INNER JOIN subjects ON studentsubjects.subject_id = subjects.id INNER JOIN users AS teachers ON subjects.teacherid = teachers.id;"
            # val = (teacher,)
            # cur.execute(sql)
            # teachers = cur.fetchall()
            # print(teachers)
            subjects = []
        else:
            sql = "SELECT * FROM users WHERE id = %s and role_id = 2"
            cur.execute(sql, (teacher,))
            teacher_exist = cur.fetchone()
            cur.execute("""SELECT DISTINCT subjects.teacherId
                                    FROM studentsubjects
                                    JOIN subjects ON studentsubjects.subject_id = subjects.id
                                    WHERE studentsubjects.student_id = %s
                                    """, (userId,))
            teacher_ids = cur.fetchall()
            print(teacher_ids)
            teacher_valid = False
            for id in teacher_ids:
                # print("Type of teacher:", int(teacher))
                # print("Type of id_tuple[0]:", type(id[0]))
                if int(teacher) == id[0]:
                    print('ni true')
                    teacher_valid = True
                    break
            # print(teacher_valid)
            if not teacher_valid:
                # print('here ako')
                flash('Teacher ID is invalid', 'danger')
                return redirect(url_for('dashboard'))

            if not teacher_exist:
                flash('Teacher ID is invalid', 'danger')
                return redirect(url_for('dashboard'))
            if(subject_id == "all"):
                # sql = "SELECT teachers.id, teachers.firstName AS teacherFirstName, teachers.lastName AS teacherLastName FROM studentsubjects INNER JOIN users AS students ON studentsubjects.student_id = students.id INNER JOIN subjects ON studentsubjects.subject_id = subjects.id INNER JOIN users AS teachers ON subjects.teacherid = teachers.id;"
                sql = "SELECT DISTINCT subjects.id, subjects.edpCode, subjects.title FROM studentsubjects INNER JOIN users AS students ON studentsubjects.student_id = students.id INNER JOIN subjects ON studentsubjects.subject_id = subjects.id INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE teachers.id = %s and subjects.id NOT IN %s and students.id = %s"
                val = (teacher, excluded_subjects, session['userId'])
                cur.execute(sql, val)
                subjects = cur.fetchall()
            else:
                cur.execute('SELECT * FROM studentsubjects WHERE student_id = %s and subject_id = %s;',
                            (userId, subject_id,))
                isInSubject = cur.fetchone()

                if not isInSubject:
                    flash("Subject chosen invalid", "danger")
                    return redirect(url_for('dashboard'))
                sql = "SELECT DISTINCT subjects.id, subjects.edpCode, subjects.title FROM studentsubjects INNER JOIN users AS students ON studentsubjects.student_id = students.id INNER JOIN subjects ON studentsubjects.subject_id = subjects.id INNER JOIN users AS teachers ON subjects.teacherid = teachers.id WHERE teachers.id = %s and subjects.id NOT IN %s and students.id = %s"
                val = (teacher, excluded_subjects, session['userId'])
                cur.execute(sql, val)
                subjects = cur.fetchall()

    # end for default queries

    cur.close()
    print(subject_id)
    if request.method == 'POST':
        print(subject_id)
        cur = mysql.connection.cursor()
        if roleId == 1:
            cur.execute("SELECT * FROM studentsubjects WHERE student_id = %s", (userId,))
            studentSubjects = cur.fetchall()
            takenAll = True
            for subject in studentSubjects:
                cur.execute(
                    "SELECT * FROM evaluation WHERE evaluationform_id = %s and idstudent = %s and subject_id = %s",
                    (evaluationFormId, userId, subject[2]))
                res = cur.fetchone()
                if res is None:
                    takenAll = False
                    break
            if takenAll:
                flash('You have evaluated all teachers!', 'success')
                return redirect(url_for('dashboard'))

        # Declaring variables for list to store rating in each section
        sec1_rating = []
        sec2_rating = []
        sec3_rating = []
        sec4_rating = []
        sec5_rating = []

        for i in range(len(section1)):
            sec1_rating.append(request.form[f'rating[{i}]'])

        for i in range(len(section2)):
            sec2_rating.append(request.form[f'rating2[{i}]'])

        for i in range(len(section3)):
            sec3_rating.append(request.form[f'rating3[{i}]'])

        for i in range(len(section4)):
            sec4_rating.append(request.form[f'rating4[{i}]'])

        for i in range(len(section5)):
            sec5_rating.append(request.form[f'rating5[{i}]'])

        # code for the translation and getting sentiment analysis
        comment = request.form.get("txtcomment")
        # comment = comment.replace("miss", "")
        print(comment)
        # getting the sentiment and details from API
        pos_val = getsentiment(comment).split(" ")[1]
        neu_val = getsentiment(comment).split(" ")[2]
        neg_val = getsentiment(comment).split(" ")[3]
        score_val = getsentiment(comment).split(" ")[4]
        sen_val = getsentiment(comment).split(" ")[0]
        # if sentiment is neutral then score = null
        if sen_val == 'neutral':
            score_val = None

        try:
            cur = mysql.connection.cursor()
            # converting list into string
            sec1_string = ','.join(sec1_rating)
            sec2_string = ','.join(sec2_rating)
            sec3_string = ','.join(sec3_rating)
            sec4_string = ','.join(sec4_rating)
            sec5_string = ','.join(sec5_rating)
            # if input comment is not empty
            if comment is not "":
                # if subject is 0 or default, get the value of first subject
                if (subject == "0" and subject != "all"):
                    subject = subjects[0][2]
                userId = session['userId']
                sql = "INSERT INTO evaluation (idteacher,idstudent,subject_id,section1,section2,section3,section4,section5,pos,neu,neg,comment,sentiment,score, evaluationform_id)\
					 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);"
                val = (teacher, userId, subject_id, sec1_string, sec2_string, sec3_string, sec4_string, sec5_string, pos_val, neu_val, neg_val, comment, sen_val, score_val, evaluationFormId,)
                print(val)
                # getting the last row id inserted in evaluation table
                # print("success")

                cur.execute(sql, val)
                mysql.connection.commit()
                print("success")
                id = cur.lastrowid
                # inserting sentiment values to table csentiment
                sql = "INSERT INTO csentiment (evaluationId,evaluationForm_id,comment,positive_value,neutral_value,negative_value,sentiment_classification,score)\
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s);"
                val = (id, evaluationFormId, comment, pos_val, neu_val, neg_val, sen_val, score_val)
                print("success")

            # else input comment is empty
            else:
                print('walay comment')
                userId = session['userId']

                sql = "INSERT INTO evaluation (idteacher,idstudent,subject_id,section1,section2,section3,section4,section5,evaluationform_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s);"
                val = (teacher, userId , subject_id, sec1_string, sec2_string, sec3_string, sec4_string, sec5_string, evaluationFormId,)
                # getting the last row id inserted in evaluation table
                print('walay comment')

                cur.execute(sql, val)
                print('walay comment')

                mysql.connection.commit()
                id = cur.lastrowid
                # inserting sentiment values to table csentiment
                # sql = "INSERT INTO csentiment (evaluationId,comment,positive_value,neutral_value,negative_value,sentiment_classification,score)\
                #                 VALUES (%s,%s,%s,%s,%s,%s,%s);"
                # val = (id, comment, pos_val, neu_val, neg_val, sen_val, score_val)

            cur.execute(sql, val)
            mysql.connection.commit()
            # cur.close()

            sql = "SELECT * FROM evaluationForms WHERE id = %s"
            val = (evaluationFormId,)
            cur.execute(sql, val)
            evaluation_forms = cur.fetchone()
            evaluationtitle = evaluation_forms[1]
            cur.close()
            flash('Successfully evaluated for evaluation ' + str(evaluationtitle), 'success' )
            return redirect("/evaluation/all/all/"+str(evaluationFormId))

        except Exception as exp:
            cur.close()
            return f'<h1>{exp}</h1>'

    else:
        return render_template("evaluation_page.html",
                               section1=section1, section2=section2,
                               lensec1=len(section1), lensec2=len(section2),
                               section3=section3, lensec3=len(section3),
                               section4=section4, lensec4=len(section4),
                               section5=section5, lensec5=len(section5),
                               teachers=teachers, subjects=subjects, rating=rating, section_details=section_details)




@app.route('/viewQuestionnaires', methods=["GET"])
def viewQuestionnaires():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    # questionnaires = []
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM questionnaireset WHERE school_id =%s and department_id = %s", (session['school_id'], session['department_id']))
    questionnaires = cur.fetchall()
    cur.close()

    #
    # for set_id in set_ids:
    #     cur.execute("SELECT questionnaireset.name, section.name, section.description, section.percentage, questionaire.question from questionnaireset INNER JOIN section ON section.questionnaireset_id = questionnaireset.id JOIN questionaire ON questionaire.questionnaireset_id = questionnaireset.id WHERE questionnaireset_id = %s", (set_id,))
    #     questionnaire = cur.fetchone()
    #     questionnaires.append(questionnaire)

    return render_template('viewQuestionnaires.html', questionnaires=questionnaires)

@app.route('/viewQuestionnaire/<questionnairesetId>', methods=["GET"])
def viewQuestionnaire(questionnairesetId):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT * FROM questionnaireset WHERE id = %s and school_id = %s and department_id = %s",
        (questionnairesetId,session['school_id'], session['department_id']))
    questionnaire = cur.fetchone()

    if not questionnaire:
        flash('Invalid questionnaire', 'danger')
        return redirect(url_for('dashboard'))



    cur.execute(
        "SELECT * FROM section WHERE questionnaireset_id = %s",
        (questionnairesetId,))
    sections = cur.fetchall()


    cur.execute("SELECT * FROM questionaire WHERE questionnaireset_id = %s and section = 1", (questionnairesetId,))
    section1 = cur.fetchall()
    cur.execute("SELECT * FROM questionaire WHERE questionnaireset_id = %s and section = 2", (questionnairesetId,))
    section2 = cur.fetchall()
    cur.execute("SELECT * FROM questionaire WHERE questionnaireset_id = %s and section = 3", (questionnairesetId,))
    section3 = cur.fetchall()
    cur.execute("SELECT * FROM questionaire WHERE questionnaireset_id = %s and section = 4", (questionnairesetId,))
    section4 = cur.fetchall()
    cur.execute("SELECT * FROM questionaire WHERE questionnaireset_id = %s and section = 5", (questionnairesetId,))
    section5 = cur.fetchall()
    cur.close()

    return render_template('viewQuestionnaire.html', questionnaire=questionnaire, section1=section1, section2=section2, section3=section3, section4=section4, section5=section5, sections=sections)

@app.route('/deleteQuestionnaire/<questionnairesetId>', methods=["POST"])
def deleteQuestionnaire(questionnairesetId):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT * FROM questionnaireset WHERE id = %s",
        (questionnairesetId,))
    questionnaire = cur.fetchone()

    if not questionnaire:
        flash('Invalid questionnaire', 'danger')
        return redirect(url_for('dashboard'))

    cur.execute('DELETE FROM questionnaireset WHERE id = %s', (questionnairesetId,))
    mysql.connection.commit()

    cur.close()
    flash('Questionnaire successfully deleted!', 'success')
    return redirect(url_for('viewQuestionnaires'))

@app.route('/viewRatingSystems', methods=["GET"])
def viewRatingSystems():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM rating WHERE school_id = %s and department_id = %s", (session['school_id'], session['department_id']))
    ratings = cur.fetchall()

    cur.close()
    return render_template('viewRatingSystems.html', ratings=ratings)

@app.route('/viewRating/<ratingid>', methods=["GET"])
def viewRating(ratingid):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM rating WHERE id = %s and school_id = %s and department_id = %s", (ratingid, session['school_id'], session['department_id']))
    rating = cur.fetchone()

    if not rating:
        flash('Invalid rating ID', 'danger')
        return redirect(url_for('dashboard'))

    cur.close()
    return render_template('viewRating.html', rating=rating)


@app.route('/deleteRating/<ratingId>', methods=["POST"])
def deleteRating(ratingId):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT * FROM rating WHERE id = %s",
        (ratingId,))
    questionnaire = cur.fetchone()

    if not questionnaire:
        flash('Invalid rating system', 'danger')
        return redirect(url_for('dashboard'))

    cur.execute('DELETE FROM rating WHERE id = %s', (ratingId,))
    mysql.connection.commit()

    cur.close()
    flash('Questionnaire successfully deleted!', 'success')
    return redirect(url_for('viewRatingSystems'))


@app.route("/editSchoolDetails/", methods=["POST", "GET"])
def editSchoolDetails():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))

    userId = session['userId']

    cur = mysql.connection.cursor()

    cur.execute("SELECT school_id FROM users WHERE id = %s", (userId,))
    school_id = cur.fetchone()

    cur.execute('SELECT * from schooldetails WHERE id = %s', (school_id[0],))
    schooldetails = cur.fetchone()

    cur.close()
    if request.method == "POST":
        # Extract data from form
        school_name = request.form['schoolName']
        address = request.form['address']
        email = request.form['email']
        contact_no = request.form['contactNo']
        userId = session['userId']
        schoolLogo = request.form['schoolLogo']

        cur = mysql.connection.cursor()

        cur.execute('SELECT id from schooldetails WHERE dean_id = %s', (userId,))
        schooldetailsid = cur.fetchone()

        cur.execute('UPDATE schooldetails SET schoolName = %s, address = %s, email = %s, contactNo = %s, schoolLogo = %s WHERE id = %s',
                    (school_name, address, email, contact_no, schoolLogo, schooldetailsid))
        mysql.connection.commit()
        cur.close()
        flash('School details updated successfully', 'success')
        return redirect(url_for('dashboard'))
    else:
        return render_template('editSchoolDetails.html', schooldetails=schooldetails)

@app.route('/register', methods=["POST", "GET"])
def register():
    return render_template("register.html")


@app.route("/generateReport/<sec1>/<sec2>/<sec3>/<sec4>/<sec5>/<comment>/<ratingPerc>/<commentPerc>/<category>/<evaluationFormId>",
           methods=["POST", "GET"])
def generateReport(sec1, sec2, sec3, sec4, sec5, comment, ratingPerc, commentPerc, category, evaluationFormId):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (session["role_id"] != 3):
        return redirect(url_for('dashboard'))
    try:
        userId = session["userId"]
        school_id = session['school_id']
        cur = mysql.connection.cursor()
        cur.execute('SELECT * from schooldetails WHERE id = %s', (school_id,))
        schooldetails = cur.fetchone()
        cur.execute('SELECT * FROM department WHERE id = %s', (session['department_id'],))
        department = cur.fetchone()
        cur.execute("SELECT esignature FROM users WHERE id = %s", (userId,))
        esignature = cur.fetchone()
        print("esig", esignature)
        if esignature[0] is None:
            flash('Unable to generate report: You must upload an e-signature (in profile)', 'danger')
            return redirect(url_for('dashboard'))
        cur.execute("SELECT id FROM questionnaireset WHERE school_id = %s and department_id = %s",
                    (session['school_id'], session['department_id']))
        questionnairesets = cur.fetchall()
        if len(questionnairesets) == 0:
            questionnairesets = [0, 0]
        questionnairesets = tuple(questionnairesets)
        cur.execute("SELECT * FROM evaluationForms WHERE id = %s and questionnaireset_id in %s", (evaluationFormId, questionnairesets))
        evaluationForm = cur.fetchone()

        if not evaluationForm:
            flash("Invalid request", "danger")
            return redirect(url_for('dashboard'))
        cur.close()
        posAve = getPositiveAverage(category)
        negAve = getNegativeAverage(category)
        neuAve = getNeutralAverage(category)

        resp = printReport(sec1, sec2, sec3, sec4, sec5, comment, posAve[0], negAve[0], neuAve[0], ratingPerc,
                           commentPerc, schooldetails, department, esignature, evaluationForm)
        return resp  # anhi na part ma download ang summary report nga pdf
    except Exception as e:
        print(e)
        return "Can't print report"


@app.route("/statistics", methods=["GET", "POST"])
def statistics():
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM department WHERE id <> 2 and id <> 3")
    departments = cur.fetchall()

    cur.execute("SELECT * FROM schoolyear")
    schoolyear = cur.fetchall()

    student_labels = ['Junior High', 'Senior High', 'College']
    school_year = 1
    semester = 1
    department = 2
    college_department = 1

    student_data = []

    if request.method == "POST":
        school_year = request.form.get('schoolYear')
        semester = request.form.get('semester')
        department = request.form.get('department')
        college_department = request.form.get('collegeDepartment')

        # Filter students based on selected filters
        query = "SELECT count(*) FROM users WHERE role_id = 1"
        if department and department != 'college':
            query += f" AND department_id = {department}"
            cur.execute("SELECT count(*) FROM users WHERE employeecategory_id = 1 and department_id = %s", (department,))
            fulltime = cur.fetchone()
            cur.execute("SELECT count(*) FROM users WHERE employeecategory_id = 2 and department_id = %s", (department,))
            parttime = cur.fetchone()

            cur.execute("SELECT name from department WHERE id = %s", (department,))
            deptName = cur.fetchone()
            student_labels = [deptName[0]]
            if department == "2":
                cur.execute(query + " AND department_id = 2")
                jhs_students = cur.fetchone()
                print('jhs', jhs_students)
                student_data = [jhs_students[0]]

            elif department == "3":
                cur.execute(query + " AND department_id = 3")
                shs_students = cur.fetchone()
                student_data = [shs_students[0]]


        elif department == 'college' and college_department:
            query += f" AND department_id = {college_department}"
            cur.execute("SELECT count(*) FROM users WHERE employeecategory_id = 1 and department_id = %s",
                        (college_department,))
            fulltime = cur.fetchone()
            cur.execute("SELECT count(*) FROM users WHERE employeecategory_id = 2 and department_id = %s",
                        (college_department,))
            parttime = cur.fetchone()
            cur.execute("SELECT name from department WHERE id = %s", (college_department,))
            deptName = cur.fetchone()
            student_labels = [deptName[0]]
            cur.execute(query + " AND department_id <> 2 AND department_id <> 3")
            college_students = cur.fetchone()
            student_data = [college_students[0]]





    else:
        cur.execute("SELECT count(*) FROM users WHERE department_id = 2 and role_id = 1")
        jhs_students = cur.fetchone()
        cur.execute("SELECT count(*) FROM users WHERE department_id = 3 and role_id = 1")
        shs_students = cur.fetchone()
        cur.execute("SELECT count(*) FROM users WHERE department_id <> 2 and department_id <> 3 and role_id = 1")
        college_students = cur.fetchone()
        cur.execute("SELECT count(*) FROM users WHERE employeecategory_id = 1")
        fulltime = cur.fetchone()
        cur.execute("SELECT count(*) FROM users WHERE employeecategory_id = 2")
        parttime = cur.fetchone()

        student_data = [jhs_students[0], shs_students[0], college_students[0]]

    respondent_data = [fulltime[0], parttime[0]]  # full time, part time

    return render_template("adminStatistics.html", departments=departments, student_data=student_data,
                           student_labels=student_labels, respondent_data=respondent_data, school_year=school_year,
                           semester=semester, schoolyear=schoolyear, department=department, college_department=college_department)


@app.route("/updateData")
def updateData():
    if 'userId' not in session:
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    cursor = mysql.connection.cursor()
    query = """
    SELECT DISTINCT(users.id), users.employeecategory_id, users.age, users.yearsExperience, 
           AVG(pos) as avg_pos, AVG(neu) as avg_neu, AVG(neg) as avg_neg, sentiment, 
           score, subject_id, evaluationForm_id 
    FROM evaluation 
    INNER JOIN users ON users.id = evaluation.idteacher 
    WHERE pos IS NOT NULL AND neu IS NOT NULL AND neg IS NOT NULL 
    GROUP BY users.id, users.employeecategory_id, users.age, users.yearsExperience, sentiment, score, subject_id, evaluationForm_id;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(rows, columns=columns)
    cursor.close()

    excel_file_path = "evaluation_statistics.xlsx"
    df.to_excel(excel_file_path, index=False, engine='openpyxl')

    flash('Data has been successfully updated and saved to Excel file.', 'success')

    file_path = 'evaluation_statistics.xlsx'
    data = pd.read_excel(file_path)

    label_encoder = LabelEncoder()
    data['sentiment'] = label_encoder.fit_transform(data['sentiment'])

    # Check the classes
    encoded_classes = label_encoder.classes_
    print("Encoded Classes:", encoded_classes)

    required_classes = ['positive', 'neutral', 'negative']
    missing_classes = [cls for cls in required_classes if cls not in encoded_classes]
    if missing_classes:
        flash(f"Warning: The following classes are missing in the encoder: {', '.join(missing_classes)}", 'danger')
    else:
        flash("All required classes are present in the encoder.", 'success')

    X = data[['age', 'employeecategory_id', 'yearsExperience']]
    y = data['sentiment']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

    clf = DecisionTreeClassifier(random_state=42)
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    report = classification_report(y_test, y_pred, target_names=label_encoder.classes_, output_dict=True)
    report_df = pd.DataFrame(report).transpose()

    report_file_path = 'classification_report.xlsx'
    report_df.to_excel(report_file_path, index=True, engine='openpyxl')
    joblib.dump(clf, 'decision_tree_model.pkl')
    joblib.dump(label_encoder, 'label_encoder.pkl')
    joblib.dump(report, 'decision_tree_report.pkl')

    logistic_regression_model = LogisticRegression(multi_class='multinomial', solver='lbfgs', max_iter=1000)
    logistic_regression_model.fit(X_train, y_train)

    y_pred = logistic_regression_model.predict(X_test)
    y_pred_proba = logistic_regression_model.predict_proba(X_test)
    report = classification_report(y_test, y_pred, target_names=label_encoder.classes_, output_dict=True)
    joblib.dump(report, 'logistic_regression_report.pkl')

    joblib.dump(logistic_regression_model, 'logistic_regression_model.pkl')
    joblib.dump(label_encoder, 'label_encoder.pkl')

    for i in range(5):
        print(f"Sample {i}: True Label: {y_test.iloc[i]}, Predicted Probabilities: {y_pred_proba[i]}")

    flash('Model trained successfully and classification report saved to Excel file.', 'success')

    return redirect(url_for('advancedEvaluationStatistics'))



@app.route('/decision_tree_report')
def decision_tree_report():
    if 'userId' not in session:
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    # Load the logistic regression report
    report = joblib.load('decision_tree_report.pkl')

    return render_template('decision_tree_report.html', report=report)

@app.route('/logistic_regression_report')
def logistic_regression_report():
    if 'userId' not in session:
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    # Load the logistic regression report
    report = joblib.load('logistic_regression_report.pkl')

    return render_template('logistic_regression_report.html', report=report)

@app.route('/predict_sentiment', methods=['POST'])
def predict_sentiment():
    age = int(request.form['age'])
    employeecategory_id = int(request.form['employeecategory_id'])
    yearsExperience = int(request.form['yearsExperience'])

    # Prepare the data for prediction
    input_data = pd.DataFrame([[age, employeecategory_id, yearsExperience]],
                              columns=['age', 'employeecategory_id', 'yearsExperience'])

    # Load the trained model
    model = joblib.load('decision_tree_model.pkl')

    # Make the prediction
    label_encoder = joblib.load('label_encoder.pkl')

    prediction = model.predict(input_data)
    sentiment = label_encoder.inverse_transform(prediction)[0]

    flash(f'The predicted sentiment for the teacher is: {sentiment}', 'success')

    return redirect(url_for('advancedEvaluationStatistics'))


@app.route('/predict_probability', methods=['POST'])
def predict_probability():
    if 'userId' not in session:
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    # Load the logistic regression model and label encoder
    logistic_regression_model = joblib.load('logistic_regression_model.pkl')
    label_encoder = joblib.load('label_encoder.pkl')

    # Get the input values from the form
    age = int(request.form['age'])
    employeecategory_id = int(request.form['employeecategory_id'])
    yearsExperience = int(request.form['yearsExperience'])

    # Create a DataFrame with the input values
    input_data = pd.DataFrame({
        'age': [age],
        'employeecategory_id': [employeecategory_id],
        'yearsExperience': [yearsExperience]
    })

    # Predict the probability of each sentiment class
    probabilities = logistic_regression_model.predict_proba(input_data)[0]

    # Get the class with the highest probability
    predicted_class = np.argmax(probabilities)
    predicted_sentiment = label_encoder.inverse_transform([predicted_class])[0]

    # Format probabilities to percentage
    formatted_probabilities = [f'{prob:.2%}' for prob in probabilities]

    probability_str = ", ".join([f'{label_encoder.inverse_transform([i])[0]}: {formatted_probabilities[i]}' for i in range(len(formatted_probabilities))])

    # Display the result
    flash(f'Predicted Sentiment: {predicted_sentiment} with probabilities {probability_str}', 'success')
    return redirect(url_for('advancedEvaluationStatistics'))

@app.route('/advancedStatistics')
def advancedEvaluationStatistics():
    if 'userId' not in session:
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    # Data for part-time vs full-time chart
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE employeecategory_id = 1")
    fulltime_ids = cur.fetchall()

    cur.execute("SELECT count(*) FROM evaluation WHERE idteacher in %s", (fulltime_ids,))
    fullTimeData = cur.fetchone()[0]

    cur.execute("SELECT id FROM users WHERE employeecategory_id = 2")
    parttime_ids = cur.fetchall()

    cur.execute("SELECT count(*) FROM evaluation WHERE idteacher in %s", (parttime_ids,))
    partTimeData = cur.fetchone()[0]

    pt_ft_data = [partTimeData, fullTimeData]  # Example: Number of part-time, Number of full-time

    # Data for online vs face-to-face classes chart
    cur.execute("SELECT id FROM questionnaireset WHERE modality = 'ONLINE'")
    onlineIds = cur.fetchall()
    cur.execute("SELECT count(*) FROM evaluationForms WHERE questionnaireset_id in %s", (onlineIds,))
    onlineCount = cur.fetchone()[0]

    cur.execute("SELECT id FROM questionnaireset WHERE modality = 'FTF'")
    ftfIds = cur.fetchall()
    cur.execute("SELECT count(*) FROM evaluationForms WHERE questionnaireset_id in %s", (ftfIds,))
    ftfCount = cur.fetchone()[0]

    online_ftf_data = [onlineCount, ftfCount]  # Example: Number of online, Number of face-to-face

    # Logistic regression results
    logistic_regression_results = [
        {"variable": "Age", "coefficient": 1.5, "p_value": 0.05},
        {"variable": "Experience", "coefficient": 2.0, "p_value": 0.01},
        # Add more results as needed
    ]
    cur.execute("SELECT id FROM questionnaireset WHERE modality = 'ONLINE'")
    online_ids = cur.fetchall()
    cur.execute("SELECT id FROM evaluationForms WHERE questionnaireset_id in %s", (online_ids,))
    online_evaluation_forms = cur.fetchall()
    cur.execute("SELECT avg(score) FROM evaluation WHERE evaluationForm_id in %s", (online_evaluation_forms,))
    online_sentiment_proportions = cur.fetchone()[0]

    cur.execute("SELECT id FROM questionnaireset WHERE modality = 'FTF'")
    ftf_ids = cur.fetchall()
    cur.execute("SELECT id FROM evaluationForms WHERE questionnaireset_id in %s", (ftf_ids,))
    ftf_evaluation_forms = cur.fetchall()
    cur.execute("SELECT avg(score) FROM evaluation WHERE evaluationForm_id in %s", (ftf_evaluation_forms,))
    ftf_sentiment_proportions = cur.fetchone()[0]


    cur.close()
    return render_template("advancedStatistics.html", pt_ft_data=pt_ft_data, online_sentiment_proportions=online_sentiment_proportions,
                           ftf_sentiment_proportions=ftf_sentiment_proportions, online_ftf_data=online_ftf_data, logistic_regression_results=logistic_regression_results)


@app.route("/deans")
def deans():
    if 'userId' not in session:
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    # Fetch departments and their deans
    cur.execute("""
        SELECT department.id, department.name, 
               CONCAT(dean.firstName, ' ', dean.lastName) as dean_name
        FROM department
        LEFT JOIN users as dean ON dean.department_id = department.id AND dean.role_id = 3
    """)
    departments = cur.fetchall()

    # Fetch users for each department
    departments_with_users = []
    for dept in departments:
        dept_id = dept[0]
        cur.execute(
            "SELECT id, CONCAT(firstName, ' ', lastName) as name FROM users WHERE (department_id = %s) AND (role_id = 2 or role_id = 3)",
            (dept_id,))
        users = cur.fetchall()
        dept_with_users = {
            'id': dept_id,
            'name': dept[1],
            'dean_name': dept[2],
            'users': users
        }
        departments_with_users.append(dept_with_users)

    cur.close()
    return render_template('deans.html', departments=departments_with_users)


@app.route('/change_dean/<int:department_id>', methods=["POST"])
def change_dean(department_id):
    if 'userId' not in session:
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    new_dean_id = request.form.get('new_dean_id')

    if not new_dean_id:
        flash('No new dean selected.', 'danger')
        return redirect(url_for('deans'))

    cur = mysql.connection.cursor()

    # Remove current dean role from the existing dean
    cur.execute("""
        UPDATE users 
        SET role_id = 2 
        WHERE department_id = %s AND role_id = 3
    """, (department_id,))

    # Assign dean role to the selected user
    cur.execute("""
        UPDATE users 
        SET role_id = 3 
        WHERE id = %s
    """, (new_dean_id,))

    mysql.connection.commit()
    cur.close()

    flash('Dean changed successfully.', 'success')
    return redirect(url_for('deans'))

@app.route('/add_dean/<int:department_id>', methods=["POST"])
def add_dean(department_id):
    if 'userId' not in session:
        return redirect(url_for('logout'))
    if session["role_id"] != 4:
        flash("Unauthorized access!", 'danger')
        return redirect(url_for('dashboard'))

    first_name = request.form.get('firstName')
    last_name = request.form.get('lastName')
    id_number = request.form.get('idNumber')
    age = request.form.get('age')
    years_experience = request.form.get('yearsExperience')

    if not all([first_name, last_name, id_number, age, years_experience]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('deans'))

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO users (firstName, lastName, password, idNumber, age, yearsExperience, role_id, department_id, school_id)
        VALUES (%s, %s, %s, %s, %s, %s, 3, %s, 1)
    """, (first_name, last_name, id_number, id_number, age, years_experience, department_id))
    mysql.connection.commit()
    cur.close()

    flash('Dean added successfully. Their password is their id number.', 'success')
    return redirect(url_for('deans'))


# functions related to /teachersevaluation
def isDefaultUrlForSummary(teacher, subject):
    if teacher == "all" and subject == "all":
        return True
    else:
        return False


# get teacher name from teacher id
def getSelectedTeacherName(teacher):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    if (teacher == "all" or teacher == "0"):
        return "All"
    else:
        cur = mysql.connection.cursor()
        sql = "SELECT firstName, lastName from users WHERE id = %s LIMIT 1"
        val = (teacher,)
        cur.execute(sql, val)
        resultTeachers = cur.fetchall()
        return resultTeachers[0][1] + ", " + resultTeachers[0][0]


# get teacher name from subject id
def getSelectedSubjectTitle(teacher, subject):
    if 'userId' not in session:
        # If there's no user_id in the session, assume session is gone and logout
        return redirect(url_for('logout'))
    cur = mysql.connection.cursor()
    if (subject == "all" or subject == "0"):
        return "All"
    else:
        if (subject == "0"):
            sql = "SELECT title from subjects WHERE teacherId = %s ORDER BY title asc LIMIT 1"
            val = (teacher,)
        else:
            sql = "SELECT edpcode,title from subjects WHERE id = %s LIMIT 1"
            val = (subject,)
        cur.execute(sql, val)
        resultSubject = cur.fetchall()
        return str(resultSubject[0][0]) + "-" + resultSubject[0][1]


# get number of respondents from filtered teacher and subject
def getNumberOfRespondents(teacher, subject, evaluationFormId, category):
    cur = mysql.connection.cursor()
    # if default
    # if no teacher is selected, and no subject select (no filter)
    if category != 'all':
        cur.execute("SELECT id FROM users WHERE employeecategory_id = %s", (category,))
        valid_teacher_ids = cur.fetchall()
        if len(valid_teacher_ids) == 0:
            valid_teacher_ids = [0,0]
            valid_teacher_ids = tuple(valid_teacher_ids)
        cur.execute("SELECT count(*) from evaluation WHERE evaluationform_id = %s and idteacher in %s", (evaluationFormId, valid_teacher_ids,))
        result = cur.fetchall()
        return result[0][0]

    if ((teacher == "all" or teacher == "0") and (subject == "0" or subject == "all")):
        cur.execute("SELECT count(*) from evaluation WHERE evaluationform_id = %s", (evaluationFormId,))
        result = cur.fetchall()
        return result[0][0]
    # if not default
    else:
        # if a teacher is selected, but no subject is selected (teacher + all subjects)
        if ((teacher != "0" or teacher != "all") and (subject == "0" or subject == "all")):
            print("na all man")
            sql = "SELECT count(*) from evaluation WHERE evaluation.idTeacher = %s and evaluationform_id = %s"
            val = (teacher, evaluationFormId,)
        # else (if there is no teacher selected and a subject is selected)
        elif ((teacher == "0" or teacher == "all") and (subject != "0" or subject != "all")):
            sql = "SELECT count(*) from evaluation WHERE evaluation.idteacher = %s and evaluationform_id = %s"
            val = (subject, evaluationFormId,)
        # if a teacher is selected, and a subject is selected (teacher + subject)
        elif ((teacher != "0" or teacher != "all") and (subject != "0" or subject != "all")):
            sql = "SELECT count(*) from evaluation WHERE evaluation.idTeacher = %s and evaluation.subject_id = %s and evaluationform_id = %s"
            val = (teacher, subject,evaluationFormId,)

        cur.execute(sql, val)
        result = cur.fetchall()
        return result[0][0]

def getNumberOfRespondentsFaculty(teacher, subject, evaluationFormId, category, respondents):
    cur = mysql.connection.cursor()
    if teacher == "all":
        flash("Invalid request. Try not to manipulate the URL please")
        return redirect(url_for('dashboard'))

    if ((teacher == "all" or teacher == "0") and (subject == "0" or subject == "all")):
        cur.execute("SELECT count(*) from evaluation WHERE evaluationform_id = %s", (evaluationFormId,))
        result = cur.fetchall()
        return result[0][0]
    # if not default
    else:
        # if a teacher is selected, but no subject is selected (teacher + all subjects)
        if ((teacher != "0" or teacher != "all") and (subject == "0" or subject == "all")):
            if respondents == "all":
                sql = "SELECT count(*) from evaluation WHERE evaluation.idTeacher = %s and evaluationform_id = %s"
                val = (teacher, evaluationFormId,)
            elif respondents == "1":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 1",
                            (session['department_id'],))
                students_id = cur.fetchall()
                sql = "SELECT count(*) from evaluation WHERE evaluation.idTeacher = %s and evaluationform_id = %s and evaluation.idstudent in %s"
                val = (teacher, evaluationFormId, students_id)
            elif respondents == "2":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 3",
                            (session['department_id'],))
                dean_id = cur.fetchone()
                sql = "SELECT count(*) from evaluation WHERE evaluation.idTeacher = %s and evaluationform_id = %s and evaluation.idstudent = %s"
                val = (teacher, evaluationFormId, dean_id)
        # else (if there is no teacher selected and a subject is selected)
        elif ((teacher == "0" or teacher == "all") and (subject != "0" or subject != "all")):
            sql = "SELECT count(*) from evaluation WHERE evaluation.idteacher = %s and evaluationform_id = %s"
            val = (subject, evaluationFormId,)
        # if a teacher is selected, and a subject is selected (teacher + subject)
        elif ((teacher != "0" or teacher != "all") and (subject != "0" or subject != "all")):
            if respondents == "all":
                sql = "SELECT count(*) from evaluation WHERE evaluation.idTeacher = %s and evaluation.subject_id = %s and evaluationform_id = %s"
                val = (teacher, subject,evaluationFormId,)
            elif respondents == "1":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 1",
                            (session['department_id'],))
                students_id = cur.fetchall()
                sql = "SELECT count(*) from evaluation WHERE evaluation.idTeacher = %s and evaluation.subject_id = %s and evaluationform_id = %s and evaluation.idstudent in %s"
                val = (teacher, subject, evaluationFormId, students_id)
            elif respondents == "2":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 3",
                            (session['department_id'],))
                dean_id = cur.fetchone()
                sql = "SELECT count(*) from evaluation WHERE evaluation.idTeacher = %s and evaluation.subject_id = %s and evaluationform_id = %s and evaluation.idstudent in %s"
                val = (teacher, subject, evaluationFormId, dean_id)
        cur.execute(sql, val)
        result = cur.fetchall()
        return result[0][0]


def getSentimentValuesFaculty(teacher, subject, evaluationFormId, category, respondents):
    cur = mysql.connection.cursor()
    if teacher == "all":
        flash("Invalid request. Try not to manipulate the URL please")
        return redirect(url_for('dashboard'))

    # if default
    # if no teacher is selected, and no subject select (no filter)
    if ((teacher == "all" or teacher == "0") and (subject == "0" or subject == "all")):
        sql = "SELECT evaluation.comment,"
        sql += "csentiment.positive_value,"
        sql += "csentiment.neutral_value,"
        sql += "csentiment.negative_value,"
        sql += "csentiment.sentiment_classification,"
        sql += "csentiment.score "
        sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
        sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.evaluationform_id = %s"
        cur.execute(sql, (evaluationFormId,))
        return cur.fetchall()
    # if not default
    else:
        # if a teacher is selected, but no subject is selected (teacher + all subjects)
        if ((teacher != "0" and teacher != "all") and (subject == "0" or subject == "all")):
            if respondents == "all":
                sql = "SELECT evaluation.comment,"
                sql += "csentiment.positive_value,"
                sql += "csentiment.neutral_value,"
                sql += "csentiment.negative_value,"
                sql += "csentiment.sentiment_classification,"
                sql += "csentiment.score "
                sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
                sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.idteacher = %s and evaluation.evaluationform_id = %s"
                val = (teacher, evaluationFormId,)
            elif respondents == "1":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 1", (session['department_id'],))
                students_id = cur.fetchall()
                sql = "SELECT evaluation.comment,"
                sql += "csentiment.positive_value,"
                sql += "csentiment.neutral_value,"
                sql += "csentiment.negative_value,"
                sql += "csentiment.sentiment_classification,"
                sql += "csentiment.score "
                sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
                sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.idteacher = %s and evaluation.evaluationform_id = %s and evaluation.idstudent in %s"
                val = (teacher, evaluationFormId, students_id)
            elif respondents == "2":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 3",
                            (session['department_id'],))
                dean_id = cur.fetchone()
                sql = "SELECT evaluation.comment,"
                sql += "csentiment.positive_value,"
                sql += "csentiment.neutral_value,"
                sql += "csentiment.negative_value,"
                sql += "csentiment.sentiment_classification,"
                sql += "csentiment.score "
                sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
                sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.idteacher = %s and evaluation.evaluationform_id = %s and evaluation.idstudent = %s"
                val = (teacher, evaluationFormId, dean_id)
        # if a teacher is selected, and a subject is selected (teacher + subject)
        elif ((teacher != "0" and teacher != "all") and (subject != "0" or subject != "all")):
            if respondents == "all":
                sql = "SELECT evaluation.comment,"
                sql += "csentiment.positive_value,"
                sql += "csentiment.neutral_value,"
                sql += "csentiment.negative_value,"
                sql += "csentiment.sentiment_classification,"
                sql += "csentiment.score "
                sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
                sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.idteacher = %s and evaluation.subject_id = %s and evaluation.evaluationform_id = %s"
                #sql = "SELECT comment,pos,neu,neg,sentiment,score from evaluation where comment is not null and comment <> '' and idteacher = %s and edpCode = %s"
                val = (teacher, subject, evaluationFormId,)
            elif respondents == "1":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 1",
                            (session['department_id'],))
                students_id = cur.fetchall()
                sql = "SELECT evaluation.comment,"
                sql += "csentiment.positive_value,"
                sql += "csentiment.neutral_value,"
                sql += "csentiment.negative_value,"
                sql += "csentiment.sentiment_classification,"
                sql += "csentiment.score "
                sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
                sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.idteacher = %s and evaluation.subject_id = %s and evaluation.evaluationform_id = %s and evaluation.idstudent in %s"
                # sql = "SELECT comment,pos,neu,neg,sentiment,score from evaluation where comment is not null and comment <> '' and idteacher = %s and edpCode = %s"
                val = (teacher, subject, evaluationFormId, students_id)
            elif respondents == "2":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 3",
                            (session['department_id'],))
                dean_id = cur.fetchone()
                sql = "SELECT evaluation.comment,"
                sql += "csentiment.positive_value,"
                sql += "csentiment.neutral_value,"
                sql += "csentiment.negative_value,"
                sql += "csentiment.sentiment_classification,"
                sql += "csentiment.score "
                sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
                sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.idteacher = %s and evaluation.subject_id = %s and evaluation.evaluationform_id = %s and evaluation.idstudent = %s"
                # sql = "SELECT comment,pos,neu,neg,sentiment,score from evaluation where comment is not null and comment <> '' and idteacher = %s and edpCode = %s"
                val = (teacher, subject, evaluationFormId, dean_id)
        # else (if there is no teacher selected and a subject is selected)
        else:
            sql = "SELECT evaluation.comment,"
            sql += "csentiment.positive_value,"
            sql += "csentiment.neutral_value,"
            sql += "csentiment.negative_value,"
            sql += "csentiment.sentiment_classification,"
            sql += "csentiment.score "
            sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
            sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.subject_id = %s and evaluation.evaluationform_id = %s"
            #sql = "SELECT comment,pos,neu,neg,sentiment,score from evaluation where comment is not null and comment <> '' and edpCode = %s"
            val = (subject, evaluationFormId,)

        cur.execute(sql, val)
        return cur.fetchall()

def getRatingValuesFaculty(teacher, subject, evaluationFormId, category, respondents):
    cur = mysql.connection.cursor()
    # if no teacher is selected, and no subject select (no filter)
    if teacher == "all":
        flash("Invalid request. Try not to manipulate the URL please")
        return redirect(url_for('dashboard'))
    if ((teacher == "all" or teacher == "0") and (subject == "0" or subject == "all")):
        cur.execute(
            "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE evaluationform_id = %s) as totalnum from evaluation WHERE evaluationForm_id = %s", (evaluationFormId,evaluationFormId,))
        return cur.fetchall()
    # if not default
    else:
        # if a teacher is selected, but no subject is selected (teacher + all subjects)
        if ((teacher != "0" and teacher != "all") and (subject == "0" or subject == "all")):
            if respondents == "all":
                sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE idteacher = %s and evaluationform_id = %s) as totalnum from evaluation WHERE idteacher = %s and evaluationForm_id = %s"
                val = (teacher, evaluationFormId,teacher,evaluationFormId,)
            elif respondents == "1":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 1",
                            (session['department_id'],))
                students_id = cur.fetchall()
                sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE idteacher = %s and evaluationform_id = %s and idstudent in %s) as totalnum from evaluation WHERE idteacher = %s and evaluationForm_id = %s and idstudent in %s"
                val = (teacher, evaluationFormId, students_id, teacher, evaluationFormId, students_id)
            elif respondents == "2":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 3",
                            (session['department_id'],))
                dean_id = cur.fetchone()
                sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE idteacher = %s and evaluationform_id = %s and idstudent = %s) as totalnum from evaluation WHERE idteacher = %s and evaluationForm_id = %s and idstudent = %s"
                val = (teacher, evaluationFormId, dean_id, teacher, evaluationFormId, dean_id)
        # if a teacher is selected, and a subject is selected (teacher + subject)
        elif ((teacher != "0" and teacher != "all") and (subject != "0" or subject != "all")):
            if respondents == "all":
                sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE idteacher = %s and subject_id = %s and evaluationform_id = %s) as totalnum from evaluation WHERE idteacher = %s and subject_id = %s and evaluationForm_id = %s"
                val = (teacher, subject, evaluationFormId, teacher, subject, evaluationFormId,)
            elif respondents == "1":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 1",
                            (session['department_id'],))
                students_id = cur.fetchall()
                sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE idteacher = %s and subject_id = %s and evaluationform_id = %s and idstudent in %s) as totalnum from evaluation WHERE idteacher = %s and subject_id = %s and evaluationForm_id = %s and idstudent in %s"
                val = (teacher, subject, evaluationFormId, students_id, teacher, subject, evaluationFormId, students_id)
            elif respondents == "2":
                cur.execute("SELECT id FROM users WHERE department_id = %s and role_id = 3",
                            (session['department_id'],))
                dean_id = cur.fetchone()
                sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE idteacher = %s and subject_id = %s and evaluationform_id = %s and idstudent = %s) as totalnum from evaluation WHERE idteacher = %s and subject_id = %s and evaluationForm_id = %s and idstudent = %s"
                val = (teacher, subject, evaluationFormId, dean_id, teacher, subject, evaluationFormId, dean_id)
        # else (if there is no teacher selected and a subject is selected)
        else:
            sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE subject_id = %s and evaluationform_id = %s) as totalnum from evaluation WHERE subject_id = %s and evaluationForm_id = %s"
            val = (subject, evaluationFormId, subject, evaluationFormId,)

        cur.execute(sql, val)
        return cur.fetchall()

# get comment,pos,neg,neu
def getSentimentValues(teacher, subject, evaluationFormId, category):
    cur = mysql.connection.cursor()
    # if default
    # if no teacher is selected, and no subject select (no filter)
    if category != 'all':
        cur.execute("SELECT id FROM users WHERE employeecategory_id = %s", (category,))
        valid_teacher_ids = cur.fetchall()
        if len(valid_teacher_ids) == 0:
            valid_teacher_ids = [0, 0]
            valid_teacher_ids = tuple(valid_teacher_ids)
        sql = "SELECT evaluation.comment,"
        sql += "csentiment.positive_value,"
        sql += "csentiment.neutral_value,"
        sql += "csentiment.negative_value,"
        sql += "csentiment.sentiment_classification,"
        sql += "csentiment.score "
        sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
        sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.evaluationform_id = %s and evaluation.idteacher in %s"
        cur.execute(sql, (evaluationFormId,valid_teacher_ids))
        return cur.fetchall()
    if ((teacher == "all" or teacher == "0") and (subject == "0" or subject == "all")):
        sql = "SELECT evaluation.comment,"
        sql += "csentiment.positive_value,"
        sql += "csentiment.neutral_value,"
        sql += "csentiment.negative_value,"
        sql += "csentiment.sentiment_classification,"
        sql += "csentiment.score "
        sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
        sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.evaluationform_id = %s"
        cur.execute(sql, (evaluationFormId,))
        return cur.fetchall()
    # if not default
    else:
        # if a teacher is selected, but no subject is selected (teacher + all subjects)
        if ((teacher != "0" and teacher != "all") and (subject == "0" or subject == "all")):
            sql = "SELECT evaluation.comment,"
            sql += "csentiment.positive_value,"
            sql += "csentiment.neutral_value,"
            sql += "csentiment.negative_value,"
            sql += "csentiment.sentiment_classification,"
            sql += "csentiment.score "
            sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
            sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.idteacher = %s and evaluation.evaluationform_id = %s"
            val = (teacher, evaluationFormId,)
        # if a teacher is selected, and a subject is selected (teacher + subject)
        elif ((teacher != "0" and teacher != "all") and (subject != "0" or subject != "all")):
            sql = "SELECT evaluation.comment,"
            sql += "csentiment.positive_value,"
            sql += "csentiment.neutral_value,"
            sql += "csentiment.negative_value,"
            sql += "csentiment.sentiment_classification,"
            sql += "csentiment.score "
            sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
            sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.idteacher = %s and evaluation.subject_id = %s and evaluation.evaluationform_id = %s"
            #sql = "SELECT comment,pos,neu,neg,sentiment,score from evaluation where comment is not null and comment <> '' and idteacher = %s and edpCode = %s"
            val = (teacher, subject, evaluationFormId,)
        # else (if there is no teacher selected and a subject is selected)
        else:
            sql = "SELECT evaluation.comment,"
            sql += "csentiment.positive_value,"
            sql += "csentiment.neutral_value,"
            sql += "csentiment.negative_value,"
            sql += "csentiment.sentiment_classification,"
            sql += "csentiment.score "
            sql += "from evaluation INNER JOIN csentiment ON evaluation.id = csentiment.evaluationId "
            sql += "where evaluation.comment is not null and evaluation.comment <> '' and evaluation.subject_id = %s and evaluation.evaluationform_id = %s"
            #sql = "SELECT comment,pos,neu,neg,sentiment,score from evaluation where comment is not null and comment <> '' and edpCode = %s"
            val = (subject, evaluationFormId,)

        cur.execute(sql, val)
        return cur.fetchall()


# get all section rating records
def getRatingValues(teacher, subject, evaluationFormId, category):
    cur = mysql.connection.cursor()
    # if default
    if category != 'all':
        cur.execute("SELECT id FROM users WHERE employeecategory_id = %s", (category,))
        valid_teacher_ids = cur.fetchall()
        if len(valid_teacher_ids) == 0:
            valid_teacher_ids = [0,0]
            valid_teacher_ids = tuple(valid_teacher_ids)
        cur.execute(
            "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE evaluationform_id = %s and idteacher in %s) as totalnum from evaluation WHERE evaluationForm_id = %s and idteacher in %s",
            (evaluationFormId, valid_teacher_ids, evaluationFormId, valid_teacher_ids))
        return cur.fetchall()
        # return result[0][0]
    # if no teacher is selected, and no subject select (no filter)
    if ((teacher == "all" or teacher == "0") and (subject == "0" or subject == "all")):
        cur.execute(
            "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE evaluationform_id = %s) as totalnum from evaluation WHERE evaluationForm_id = %s", (evaluationFormId,evaluationFormId,))
        return cur.fetchall()
    # if not default
    else:
        # if a teacher is selected, but no subject is selected (teacher + all subjects)
        if ((teacher != "0" and teacher != "all") and (subject == "0" or subject == "all")):
            sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE idteacher = %s and evaluationform_id = %s) as totalnum from evaluation WHERE idteacher = %s and evaluationForm_id = %s"
            val = (teacher, evaluationFormId,teacher,evaluationFormId,)
        # if a teacher is selected, and a subject is selected (teacher + subject)
        elif ((teacher != "0" and teacher != "all") and (subject != "0" or subject != "all")):
            sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE idteacher = %s and subject_id = %s and evaluationform_id = %s) as totalnum from evaluation WHERE idteacher = %s and subject_id = %s and evaluationForm_id = %s"
            val = (teacher, subject, evaluationFormId, teacher, subject, evaluationFormId,)
        # else (if there is no teacher selected and a subject is selected)
        else:
            sql = "select section1, section2, section3, section4, section5, (select count(id) from evaluation WHERE subject_id = %s and evaluationform_id = %s) as totalnum from evaluation WHERE subject_id = %s and evaluationForm_id = %s"
            val = (subject, evaluationFormId, subject, evaluationFormId,)

        cur.execute(sql, val)
        return cur.fetchall()


# getting average for positive, negative and neutral
def getPositiveAverage(category):
    teacher = G_TEACHER_ID
    subject = G_SUBJECT_ID
    evaluationFormId = G_EVALUATION_FORM_ID

    cur = mysql.connection.cursor()
    # if default
    if category != 'all':
        print("CATEGORY ID: ", category)
        cur.execute("SELECT id FROM users WHERE employeecategory_id = %s and department_id = %s", (category, session["department_id"]))
        valid_teacher_ids = cur.fetchall()
        if len(valid_teacher_ids) == 0:
            valid_teacher_ids = [0,0]
            valid_teacher_ids = tuple(valid_teacher_ids)
        cur.execute(
            "SELECT AVG(positive_value), evaluation.idteacher "
            "FROM csentiment "
            "INNER JOIN evaluation ON evaluation.id = csentiment.evaluationId "
            "WHERE csentiment.score IS NOT NULL "
            "AND csentiment.evaluationform_id = %s "
            "AND evaluation.idteacher in %s"
            "GROUP BY evaluation.idteacher",
            (evaluationFormId, valid_teacher_ids)
        )
        posAve = cur.fetchall()
        posAverage = 0
        for i in range(len(valid_teacher_ids)):
            posAverage += posAve[i][0]

        if len(valid_teacher_ids) != 0:
            posAverage = posAverage / len(valid_teacher_ids)
        else:
            posAverage = 0

        posAverage = (posAverage, 0)
        print(posAverage)
        return posAverage
    # if no teacher is selected, and no subject select (no filter)
    if ((teacher == "all" or teacher == "0") and (subject == "0" or subject == "all")):
        cur.execute("SELECT AVG(positive_value) from csentiment WHERE score IS NOT NULL and csentiment.evaluationform_id = %s", (evaluationFormId,))
        posAve = cur.fetchall()[0]
        return posAve
    # if not default
    else:
        # if a teacher is selected, but no subject is selected (teacher + all subjects)
        if ((teacher != "0" and teacher != "all") and (subject == "0" or subject == "all")):
            sql = "SELECT AVG(csentiment.positive_value) "
            sql += "from csentiment INNER JOIN evaluation ON "
            sql += "csentiment.evaluationId = evaluation.id "
            sql += "where evaluation.idteacher = %s and csentiment.score IS NOT NULL and csentiment.evaluationform_id = %s"
            val = (teacher, evaluationFormId,)
        # if a teacher is selected, and a subject is selected (teacher + subject)
        elif ((teacher != "0" and teacher != "all") and (subject != "0" or subject != "all")):
            sql = "SELECT AVG(csentiment.positive_value) "
            sql += "from csentiment INNER JOIN evaluation ON "
            sql += "csentiment.evaluationId = evaluation.id "
            sql += "where evaluation.idteacher = %s and evaluation.subject_id = %s and csentiment.score IS NOT NULL and csentiment.evaluationform_id = %s"
            #sql = "SELECT AVG(pos) from evaluation where idteacher = %s and edpCode = %s and score IS NOT NULL "
            val = (teacher, subject, evaluationFormId,)
        # else (if there is no teacher selected and a subject is selected)
        else:
            sql = "SELECT AVG(csentiment.positive_value) "
            sql += "from csentiment INNER JOIN evaluation ON "
            sql += "csentiment.evaluationId = evaluation.id "
            sql += "where evaluation.subject_id = %s and csentiment.score IS NOT NULL and csentiment.evaluationform_id = %s"
            #sql = "SELECT AVG(pos) from evaluation where edpCode = %s and score IS NOT NULL "
            val = (subject, evaluationFormId)

        cur.execute(sql, val)
        posAve = cur.fetchall()[0]
        print(type(posAve))
        return posAve


def getNegativeAverage(category):
    teacher = G_TEACHER_ID
    subject = G_SUBJECT_ID
    evaluationFormId = G_EVALUATION_FORM_ID

    cur = mysql.connection.cursor()
    # if default
    if category != 'all':
        print("CATEGORY ID: ", category)
        cur.execute("SELECT id FROM users WHERE employeecategory_id = %s and department_id = %s", (category, session["department_id"]))
        valid_teacher_ids = cur.fetchall()
        if len(valid_teacher_ids) == 0:
            valid_teacher_ids = [0,0]
            valid_teacher_ids = tuple(valid_teacher_ids)
        cur.execute(
            "SELECT AVG(negative_value), evaluation.idteacher "
            "FROM csentiment "
            "INNER JOIN evaluation ON evaluation.id = csentiment.evaluationId "
            "WHERE csentiment.score IS NOT NULL "
            "AND csentiment.evaluationform_id = %s "
            "AND evaluation.idteacher in %s"
            "GROUP BY evaluation.idteacher",
            (evaluationFormId, valid_teacher_ids)
        )
        negAve = cur.fetchall()
        negAverage = 0
        for i in range(len(valid_teacher_ids)):
            negAverage += negAve[i][0]

        if len(valid_teacher_ids) != 0:
            negAverage = negAverage / len(valid_teacher_ids)
        else:
            negAverage = 0

        negAverage = (negAverage, 0)
        return negAverage

    # if no teacher is selected, and no subject select (no filter)
    if ((teacher == "all" or teacher == "0") and (subject == "0" or subject == "all")):
        cur.execute("SELECT AVG(csentiment.negative_value) from csentiment WHERE score IS NOT NULL and csentiment.evaluationform_id = %s", (evaluationFormId,))
        posAve = cur.fetchall()[0]
        return posAve
    # if not default
    else:
        # if a teacher is selected, but no subject is selected (teacher + all subjects)
        if ((teacher != "0" and teacher != "all") and (subject == "0" or subject == "all")):
            sql = "SELECT AVG(csentiment.negative_value) "
            sql += "from csentiment INNER JOIN evaluation ON "
            sql += "csentiment.evaluationId = evaluation.id "
            sql += "where evaluation.idteacher = %s and csentiment.score IS NOT NULL and csentiment.evaluationform_id = %s"
            val = (teacher, evaluationFormId,)
        # if a teacher is selected, and a subject is selected (teacher + subject)
        elif ((teacher != "0" and teacher != "all") and (subject != "0" or subject != "all")):
            sql = "SELECT AVG(csentiment.negative_value) "
            sql += "from csentiment INNER JOIN evaluation ON "
            sql += "csentiment.evaluationId = evaluation.id "
            sql += "where evaluation.idteacher = %s and evaluation.subject_id = %s and csentiment.score IS NOT NULL and csentiment.evaluationform_id = %s"
            #sql = "SELECT AVG(pos) from evaluation where idteacher = %s and edpCode = %s and score IS NOT NULL "
            val = (teacher, subject, evaluationFormId,)
        # else (if there is no teacher selected and a subject is selected)
        else:
            sql = "SELECT AVG(csentiment.negative_value) "
            sql += "from csentiment INNER JOIN evaluation ON "
            sql += "csentiment.evaluationId = evaluation.id "
            sql += "where evaluation.subject_id = %s and csentiment.score IS NOT NULL and csentiment.evaluationform_id = %s"
            #sql = "SELECT AVG(pos) from evaluation where edpCode = %s and score IS NOT NULL "
            val = (subject, evaluationFormId,)

        cur.execute(sql, val)
        negAve = cur.fetchall()[0]
        return negAve


def getNeutralAverage(category):
    teacher = G_TEACHER_ID
    subject = G_SUBJECT_ID
    evaluationFormId = G_EVALUATION_FORM_ID

    cur = mysql.connection.cursor()

    # if default
    if category != 'all':
        print("CATEGORY ID: ", category)
        cur.execute("SELECT id FROM users WHERE employeecategory_id = %s and department_id = %s", (category, session["department_id"]))
        valid_teacher_ids = cur.fetchall()
        if len(valid_teacher_ids) == 0:
            valid_teacher_ids = [0,0]
            valid_teacher_ids = tuple(valid_teacher_ids)
        cur.execute(
            "SELECT AVG(neutral_value), evaluation.idteacher "
            "FROM csentiment "
            "INNER JOIN evaluation ON evaluation.id = csentiment.evaluationId "
            "WHERE csentiment.score IS NOT NULL "
            "AND csentiment.evaluationform_id = %s "
            "AND evaluation.idteacher in %s"
            "GROUP BY evaluation.idteacher",
            (evaluationFormId, valid_teacher_ids)
        )
        neuAve = cur.fetchall()
        neuAverage = 0
        for i in range(len(valid_teacher_ids)):
            neuAverage += neuAve[i][0]

        if len(valid_teacher_ids) != 0:
            neuAverage = neuAverage / len(valid_teacher_ids)
        else:
            neuAverage = 0

        print(neuAverage)
        neuAverage = (neuAverage, 0)
        return neuAverage

    # if no teacher is selected, and no subject select (no filter)
    if ((teacher == "all" or teacher == "0") and (subject == "0" or subject == "all")):
        cur.execute("SELECT AVG(csentiment.neutral_value) from csentiment WHERE score IS NOT NULL and csentiment.evaluationform_id = %s", (evaluationFormId,))
        posAve = cur.fetchall()[0]
        return posAve
    # if not default
    else:
        # if a teacher is selected, but no subject is selected (teacher + all subjects)
        if ((teacher != "0" and teacher != "all") and (subject == "0" or subject == "all")):
            sql = "SELECT AVG(csentiment.neutral_value) "
            sql += "from csentiment INNER JOIN evaluation ON "
            sql += "csentiment.evaluationId = evaluation.id "
            sql += "where evaluation.idteacher = %s and csentiment.score IS NOT NULL and csentiment.evaluationform_id = %s"
            val = (teacher, evaluationFormId,)
        # if a teacher is selected, and a subject is selected (teacher + subject)
        elif ((teacher != "0" and teacher != "all") and (subject != "0" or subject != "all")):
            sql = "SELECT AVG(csentiment.neutral_value) "
            sql += "from csentiment INNER JOIN evaluation ON "
            sql += "csentiment.evaluationId = evaluation.id "
            sql += "where evaluation.idteacher = %s and evaluation.subject_id = %s and csentiment.score IS NOT NULL  and csentiment.evaluationform_id = %s"
            #sql = "SELECT AVG(pos) from evaluation where idteacher = %s and edpCode = %s and score IS NOT NULL "
            val = (teacher, subject, evaluationFormId,)
        # else (if there is no teacher selected and a subject is selected)
        else:
            sql = "SELECT AVG(csentiment.neutral_value) "
            sql += "from csentiment INNER JOIN evaluation ON "
            sql += "csentiment.evaluationId = evaluation.id "
            sql += "where evaluation.subject_id = %s and csentiment.score IS NOT NULL and csentiment.evaluationform_id = %s"
            #sql = "SELECT AVG(pos) from evaluation where edpCode = %s and score IS NOT NULL "
            val = (subject, evaluationFormId)

    cur.execute(sql, val)
    neuAve = cur.fetchall()[0]
    return neuAve


# end for getting average for positive, negative and neutral


# method that will send the input comment to the API and return its response
with app.app_context():
    def getsentiment(comment):
        dictToSend = {'comment': comment}
        res = requests.post('http://127.0.0.1:8000/getSentiment', json=dictToSend)
        #res = requests.post('https://csentiment-api.herokuapp.com/getSentiment', json=dictToSend)
        print('response from server:', res.text)
        print(f'Status Code: {res.status_code}')
        print(f'Response: {res.json()}')
        dictFromServer = res.json()
        return str(dictFromServer)

with app.app_context():
    def printReport(sec1, sec2, sec3, sec4, sec5, comment, posAve, negAve, neuAve, ratingPerc, commentPerc, schooldetails, department, esignature, evaluationForm):
        import requests
        evaluationFormId = G_EVALUATION_FORM_ID
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM evaluationForms WHERE id = %s", (evaluationFormId,))
        evaluationForm = cur.fetchone()

        ratingId = evaluationForm[7]
        semesterId = evaluationForm[5]
        schoolyearId = evaluationForm[6]
        questionnairesetId = evaluationForm[4]
        cur.execute("SELECT * FROM rating WHERE id = %s", (ratingId,))
        rating = cur.fetchone()
        range5Array = [float(x) for x in rating[10].split('-')]
        range4Array = [float(x) for x in rating[8].split('-')]
        range3Array = [float(x) for x in rating[6].split('-')]
        range2Array = [float(x) for x in rating[4].split('-')]
        range1Array = [float(x) for x in rating[2].split('-')]
        cur.execute("SELECT * FROM semester WHERE id = %s", (semesterId,))
        semester = cur.fetchone()
        cur.execute("SELECT * FROM schoolyear WHERE id = %s", (schoolyearId,))
        schoolyear = cur.fetchone()

        cur.execute("SELECT percentage FROM section WHERE section = 1 and questionnaireset_id = %s", (questionnairesetId,))
        sec1Percentage = cur.fetchone()

        cur.execute("SELECT percentage FROM section WHERE section = 2 and questionnaireset_id = %s",
                    (questionnairesetId,))
        sec2Percentage = cur.fetchone()

        cur.execute("SELECT percentage FROM section WHERE section = 3 and questionnaireset_id = %s",
                    (questionnairesetId,))
        sec3Percentage = cur.fetchone()

        cur.execute("SELECT percentage FROM section WHERE section = 4 and questionnaireset_id = %s",
                    (questionnairesetId,))
        sec4Percentage = cur.fetchone()

        cur.execute("SELECT percentage FROM section WHERE section = 5 and questionnaireset_id = %s",
                    (questionnairesetId,))
        sec5Percentage = cur.fetchone()

        cur.execute("SELECT name FROM section WHERE section = 1 and questionnaireset_id = %s",
                    (questionnairesetId,))
        sec1Name = cur.fetchone()

        cur.execute("SELECT name FROM section WHERE section = 2 and questionnaireset_id = %s",
                    (questionnairesetId,))
        sec2Name = cur.fetchone()

        cur.execute("SELECT name FROM section WHERE section = 3 and questionnaireset_id = %s",
                    (questionnairesetId,))
        sec3Name = cur.fetchone()

        cur.execute("SELECT name FROM section WHERE section = 4 and questionnaireset_id = %s",
                    (questionnairesetId,))
        sec4Name = cur.fetchone()

        cur.execute("SELECT name FROM section WHERE section = 5 and questionnaireset_id = %s",
                    (questionnairesetId,))
        sec5Name = cur.fetchone()

        category_id = G_CATEGORY_NAME
        categoryName = 'all'
        if category_id != 'all':
            cur.execute("SELECT name FROM employeecategory WHERE id = %s", (category_id,))
            categoryName = cur.fetchone()
        test = {
            'Section1': sec1,
            'Section2': sec2,
            'Section3': sec3,
            'Section4': sec4,
            'Section5': sec5,
            'Comments': comment,
            'Teacher': G_TEACHER_NAME,
            'Subject': G_SUBJECT_NAME,
            'Respondents': G_NUMBER_OF_RESPONDENTS,
            'posAve': posAve,
            'negAve': negAve,
            'neuAve': neuAve,
            'ratingPercentage': ratingPerc,
            'commentPercentage': commentPerc,
            'evaluationForm': evaluationForm[1],
            'rating': rating,
            'schoolyear': schoolyear[1],
            'semester': semester[1],
            'schooldetails': schooldetails,
            'range5Array': range5Array,
            'range4Array': range4Array,
            'range3Array': range3Array,
            'range2Array': range2Array,
            'range1Array': range1Array,
            'department': department[1],
            'categoryName': categoryName,
            'esignature': esignature,
            'sec1Perc': sec1Percentage,
            'sec2Perc': sec2Percentage,
            'sec3Perc': sec3Percentage,
            'sec4Perc': sec4Percentage,
            'sec5Perc': sec5Percentage,
            'sec1Name': sec1Name,
            'sec2Name': sec2Name,
            'sec3Name': sec3Name,
            'sec4Name': sec4Name,
            'sec5Name': sec5Name,

        }
        # data = [
        #     ("Section1", sec1),
        #     ("Section2", sec2),
        #     ("Section3", sec3),
        #     ("Section4", sec4),
        #     ("Section5", sec5),
        #     ("Comments", comment),
        #     ("Teacher", G_TEACHER_NAME),
        #     ("Subject", G_SUBJECT_NAME),
        #     ("Respondents", G_NUMBER_OF_RESPONDENTS),
        #     ("posAve", posAve),
        #     ("negAve", negAve),
        #     ("neuAve", neuAve),
        # ]
        # data = list(test.items())
        cur.close()
        resp = requests.post('http://127.0.0.1:8000/reportGeneration', json=test, stream=True)
        #resp = requests.post('https://csentimentapi.herokuapp.com/reportGeneration', json=data, stream=True)
        return resp.raw.read(), resp.status_code, resp.headers.items()

if __name__ == "__main__":
    # app.run(debug=True)
    # app.run(host='127.0.0.1', port=5000, debug=True)
    app.run()