from flask import render_template

def index():
    return render_template('index.html')

def course(course_id):
    return render_template('course.html', course_id=course_id)