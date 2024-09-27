# Introduction

- **Course name**: Database System-113
- **Teacher**: 蔡昀琤
- **Student**: 科技115陳廷安
- **Student id**: 41171214H

# HW1 User Registration and Login System

 **[link](https://youtu.be/LT-PYBJTzqM)**

This project is a basic user registration and login system built using **Flask** as the web framework and **MySQL** as the database. The system allows users to register, log in, and access a dashboard. The passwords are securely hashed using the `pbkdf2:sha256` method, and the system ensures no duplicate usernames or emails are allowed.

## Features

- **User Registration**: Users can create a new account by providing a name, email, and password. The system checks for unique emails and usernames.
- **User Login**: Registered users can log in using their credentials.
- **Password Security**: Passwords are securely hashed using `pbkdf2:sha256`.
- **Dashboard**: Once logged in, users are redirected to a dashboard where their information is displayed.
- **User Logout**: Users can log out, clearing their session.

## Application Structure

- **app.py**: The main Flask application containing routes for registration, login, dashboard, and logout functionality.
- **templates/**: Directory containing HTML files (register, login, dashboard).
  - `register.html`: The registration form.
  - `login.html`: The login form.
  - `dashboard.html`: Displays user information after login.
- **README.md**: Project documentation.

## Routes

- `/`: User registration page (also acts as the home page).
- `/login`: User login page.
- `/dashboard`: User dashboard page (accessible after login).
- `/logout`: Logs out the user and redirects to the login page.

