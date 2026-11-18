from flask import Blueprint, render_template
page_bp=Blueprint('pages',__name__)

@page_bp.get('/')
def dashboard():
    return render_template('dashboard.html')

@page_bp.get('/users')
def users():
    return render_template('users.html')

@page_bp.get('/login')
def login_page():
    return render_template('login.html')

@page_bp.get('/courses')
def courses_page():
    return render_template('courses.html')

@page_bp.get('/sessions')
def sessions_page():
    return render_template('sessions.html')

@page_bp.get('/imports')
def imports_page():
    return render_template('imports.html')

@page_bp.get('/analytics')
def analytics_page():
    return render_template('analytics.html')

@page_bp.get('/account')
def account_page():
    return render_template('account.html')

