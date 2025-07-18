
from flask import Flask, flash, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here' 

# SQLite configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messages.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Message model
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.String(20), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='messages')
    
    def __repr__(self):
        return f'<Message by {self.user_id}: {self.text}>'

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)   

    def __repr__(self):
        return f'<User {self.username}'


# Initialize database (only needed once)
with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user = User.query.filter_by(username=session.get('username')).first()
        message = request.form.get('message','').strip()
        
        if not message:
            flash('Message cannot be empty.')
            return redirect(url_for('index'))
        elif len(message) > 100:
            flash('Message is too long (max 100 characters).')
            return redirect(url_for('index'))
        elif not session.get('username'):
            flash('You must be logged in to post a message')
            return redirect(url_for('login'))
        else:
            user = User.query.filter_by(username=session['username']).first()
            new_message = Message(text=message, timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"), user_id=user.id)
            db.session.add(new_message)
            db.session.commit()
            return redirect(url_for('index'))

    q = request.args.get('q', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 5

    query = Message.query
    if q:
        query = query.filter(Message.text.ilike(f"%{q}%"))
    query = query.order_by(Message.id.desc())

    total = query.count()
    messages = query.offset((page-1)*per_page).limit(per_page).all()
    total_pages = (total // per_page) + (1 if total % per_page else 0)

    return render_template('index.html', messages=messages, page=page, total=total, total_pages=total_pages, per_page=per_page, q=q)

@app.route('/delete/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    user = User.query.filter_by(username=session.get('username')).first()

    if message.user_id != user.id:
        flash("You can only delete your won messages.")
        return redirect(url_for('index'))

    db.session.delete(message)
    db.session.commit()
    flash('Message deleted.')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not email or not password:
            flash('All fields are required.')
            return redirect(url_for('register'))
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.')
            return redirect(url_for('register'))
        
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already registered.')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! You can now log in.')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid username or password')
            return redirect(url_for('login'))

        session['username'] = user.username
        flash('Logged in secessfully')
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    flash('Logged out successfully')
    return redirect(url_for('index'))

@app.route('/user/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    messages = Message.query.filter_by(user_id=user.id).order_by(Message.id.desc()).all()
    return render_template('profile.html', user=user, messages=messages)

@app.route('/change-username', methods=['GET', 'POST'])
def change_username():
    if 'username' not in session:
        flash("You must be logged in to change your username.")
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()

    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()

        if not new_username:
            flash("Username cannot be empty.")
            return redirect(url_for('change_username'))

        if new_username == user.username:
            flash("You entered the same username.")
            return redirect(url_for('change_username'))

        if User.query.filter_by(username=new_username).first():
            flash("That username is already taken.")
            return redirect(url_for('change_username'))

        # Update
        user.username = new_username
        session['username'] = new_username
        db.session.commit()
        flash("Username updated successfully.")
        return redirect(url_for('user_profile', username=new_username))

    return render_template('change_username.html', current_username=user.username)

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
        flash("You must be logged in to change your password.")
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()

    if request.method == 'POST':
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not check_password_hash(user.password_hash, current_password):
            flash('Current password is incorrect.')
        elif new_password != confirm_password:
            flash('New passwords do not match.')
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password changed successfully.')
            return redirect(url_for('user_profile', username=user.username))

    return render_template('change_password.html')

if __name__ == '__main__':
    app.run(debug=True)