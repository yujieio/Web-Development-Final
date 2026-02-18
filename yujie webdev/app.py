from flask import Flask, render_template, request, redirect, url_for, flash, abort, session, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime
import os
import io
import csv
import sqlite3
import math
import random
from sqlalchemy import or_, text, inspect

# Force templates from THIS folder - works even if you run from another directory
_script_dir = os.path.dirname(os.path.abspath(__file__))
_template_dir = os.path.join(_script_dir, 'templates')
app = Flask(__name__, template_folder=_template_dir, static_folder=os.path.join(_script_dir, 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key_change_in_production')
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
app.config['TEMPLATES_AUTO_RELOAD'] = app.config['DEBUG']

# ---------------------------------------------------------
# DATABASE CONFIGURATION
# ---------------------------------------------------------
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'project.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads', 'profiles')
app.config['MEMORY_UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads', 'memories')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
os.makedirs(app.config['MEMORY_UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------------------------------------------------------
# MODELS
# ---------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    user_type = db.Column(db.String(20), nullable=False, default='Youth')  # 'Youth' or 'Senior'
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class SkillPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    skill_type = db.Column(db.String(20), nullable=False) # 'Offer' or 'Request'
    user_type = db.Column(db.String(20), nullable=False)  # 'Youth' or 'Senior'
    author_name = db.Column(db.String(100), nullable=True)  # Author's name
    profile_picture_url = db.Column(db.String(500), nullable=True)  # Profile picture URL
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Link to user account
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Link to user account
    profile_picture_url = db.Column(db.String(500), nullable=True)  # Uploaded profile picture
    name = db.Column(db.String(100), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'Youth' or 'Senior'
    languages = db.Column(db.String(200), nullable=True)  # Comma-separated
    short_intro = db.Column(db.Text, nullable=True)
    interaction_type = db.Column(db.String(20), default='1-to-1')  # '1-to-1' or 'Group'
    meeting_style = db.Column(db.String(20), default='Online')  # 'Online' or 'In-Person'
    interest_tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags
    large_text = db.Column(db.Boolean, default=False)
    high_contrast = db.Column(db.Boolean, default=False)
    easy_reading = db.Column(db.Boolean, default=False)
    total_points = db.Column(db.Integer, default=0)  # Total points accumulated by user
    name_style = db.Column(db.String(50), default='default')  # Shop: default, rainbow, gradient, neon, gold, cursive, ocean
    is_active = db.Column(db.Boolean, default=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BingoPrompt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prompt_text = db.Column(db.String(200), nullable=False)
    position = db.Column(db.Integer, nullable=False)  # Position on board (1-25 for 5x5 grid)
    category = db.Column(db.String(50), nullable=True)  # Optional category
    is_active = db.Column(db.Boolean, default=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class BingoStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prompt_id = db.Column(db.Integer, db.ForeignKey('bingo_prompt.id'), nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'Youth' or 'Senior'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Link to user account
    title = db.Column(db.String(200), nullable=False)
    story_content = db.Column(db.Text, nullable=False)
    photo_url = db.Column(db.String(500), nullable=True)  # Optional photo
    points_earned = db.Column(db.Integer, default=10)  # Points for posting
    likes_count = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BingoComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('bingo_story.id'), nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Link to user account
    comment_text = db.Column(db.Text, nullable=False)
    points_earned = db.Column(db.Integer, default=2)  # Points for commenting
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

class BingoStoryLike(db.Model):
    """Max 1 like per account per story."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    story_id = db.Column(db.Integer, db.ForeignKey('bingo_story.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'story_id', name='uq_bingo_story_like_user_story'),)

class UserPurchase(db.Model):
    """Bingo shop purchases - font/name styles."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_key = db.Column(db.String(50), nullable=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ntype = db.Column(db.String(50), nullable=False)  # 'comment', 'help_offer', 'offer_accepted'
    title = db.Column(db.String(200), nullable=True)
    message = db.Column(db.Text, nullable=True)
    link_url = db.Column(db.String(500), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    help_request_id = db.Column(db.Integer, nullable=True)  # Scope: same help request = same chat
    skill_post_id = db.Column(db.Integer, nullable=True)    # Scope: same skill post = same chat
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.String(50), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    event_type = db.Column(db.String(50), nullable=False)  # 'Physical' or 'Online'
    organizer_name = db.Column(db.String(100), nullable=True)  # Poster from logged-in profile
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Link to creator
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(50), nullable=True)
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.Column(db.String(100), nullable=False)
    likes = db.Column(db.Integer, default=0)
    liked_by = db.Column(db.String(500), default='')  # Comma-separated list of usernames who liked

class MemoryItem(db.Model):
    """WDP-style memory album: title, caption, uploaded photo."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(500), nullable=False)
    uploader = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

# Create Database Tables and run migrations
with app.app_context():
    db.create_all()
    
    # Migration: Add missing columns to existing tables
    try:
        inspector = inspect(db.engine)
        
        # Add total_points to user_profile
        up_cols = [col['name'] for col in inspector.get_columns('user_profile')]
        if 'total_points' not in up_cols:
            db.session.execute(text('ALTER TABLE user_profile ADD COLUMN total_points INTEGER DEFAULT 0'))
            db.session.commit()
        if 'user_id' not in up_cols:
            db.session.execute(text('ALTER TABLE user_profile ADD COLUMN user_id INTEGER'))
            db.session.commit()
        if 'profile_picture_url' not in up_cols:
            db.session.execute(text('ALTER TABLE user_profile ADD COLUMN profile_picture_url VARCHAR(500)'))
            db.session.commit()
        if 'name_style' not in up_cols:
            db.session.execute(text('ALTER TABLE user_profile ADD COLUMN name_style VARCHAR(50) DEFAULT \'default\''))
            db.session.commit()
        
        # Create user_purchase table for bingo shop
        try:
            tables = inspector.get_table_names()
            if 'user_purchase' not in tables:
                db.session.execute(text('''CREATE TABLE IF NOT EXISTS user_purchase (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    item_key VARCHAR(50) NOT NULL,
                    purchased_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )'''))
                db.session.commit()
        except Exception:
            pass
        
        # Add user_id to skill_post
        sp_cols = [col['name'] for col in inspector.get_columns('skill_post')]
        if 'user_id' not in sp_cols:
            db.session.execute(text('ALTER TABLE skill_post ADD COLUMN user_id INTEGER'))
            db.session.commit()
        
        # Add user_id to bingo_story
        bs_cols = [col['name'] for col in inspector.get_columns('bingo_story')]
        if 'user_id' not in bs_cols:
            db.session.execute(text('ALTER TABLE bingo_story ADD COLUMN user_id INTEGER'))
            db.session.commit()
        
        # Add user_id to bingo_comment
        bc_cols = [col['name'] for col in inspector.get_columns('bingo_comment')]
        if 'user_id' not in bc_cols:
            db.session.execute(text('ALTER TABLE bingo_comment ADD COLUMN user_id INTEGER'))
            db.session.commit()
        
        # Add organizer_name and user_id to event
        try:
            ev_cols = [col['name'] for col in inspector.get_columns('event')]
            if 'organizer_name' not in ev_cols:
                db.session.execute(text('ALTER TABLE event ADD COLUMN organizer_name VARCHAR(100)'))
                db.session.commit()
            if 'user_id' not in ev_cols:
                db.session.execute(text('ALTER TABLE event ADD COLUMN user_id INTEGER'))
                db.session.commit()
        except Exception:
            pass

        # Create chat_message table if it doesn't exist
        try:
            tables = inspector.get_table_names()
            if 'chat_message' not in tables:
                db.session.execute(text('''CREATE TABLE IF NOT EXISTS chat_message (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    help_request_id INTEGER,
                    skill_post_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES user(id),
                    FOREIGN KEY (receiver_id) REFERENCES user(id)
                )'''))
                db.session.commit()
        except Exception:
            pass

        # Add help_request_id, skill_post_id to chat_message if missing
        try:
            cm_cols = [c['name'] for c in inspector.get_columns('chat_message')]
            if 'help_request_id' not in cm_cols:
                db.session.execute(text('ALTER TABLE chat_message ADD COLUMN help_request_id INTEGER'))
                db.session.commit()
            if 'skill_post_id' not in cm_cols:
                db.session.execute(text('ALTER TABLE chat_message ADD COLUMN skill_post_id INTEGER'))
                db.session.commit()
        except Exception:
            pass

        # Create notification table if it doesn't exist
        try:
            tables = inspector.get_table_names()
            if 'notification' not in tables:
                db.session.execute(text('''CREATE TABLE IF NOT EXISTS notification (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    ntype VARCHAR(50) NOT NULL,
                    title VARCHAR(200),
                    message TEXT,
                    link_url VARCHAR(500),
                    is_read INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )'''))
                db.session.commit()
        except Exception:
            pass
    except Exception:
        db.session.rollback()

# ---------------------------------------------------------
# AUTHENTICATION HELPERS
# ---------------------------------------------------------
def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_logged_in_user():
    """Get the currently logged-in User object."""
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user is None:
            # User was deleted (e.g. after database reset) - clear stale session
            session.clear()
            return None
        return user
    return None

def get_logged_in_profile():
    """Get the UserProfile for the currently logged-in user."""
    user = get_logged_in_user()
    if user:
        return UserProfile.query.filter_by(user_id=user.id, is_active=True).first()
    return None

DEFAULT_AVATAR = 'images/default-avatar.svg'

def get_profile_picture_url(profile):
    """Return profile picture URL (custom or default)."""
    if profile and profile.profile_picture_url:
        return profile.profile_picture_url
    return url_for('static', filename=DEFAULT_AVATAR)

def create_notification(user_id, ntype, title, message, link_url=None):
    """Create a notification for a user."""
    try:
        n = Notification(user_id=user_id, ntype=ntype, title=title, message=message, link_url=link_url)
        db.session.add(n)
        db.session.commit()
    except Exception:
        db.session.rollback()

def get_unread_notification_count(user_id):
    """Get count of unread notifications for user."""
    if not user_id:
        return 0
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Bingo Shop - name/font styles purchasable with points
BINGO_SHOP_ITEMS = [
    {'key': 'rainbow', 'name': 'Rainbow Spectrum', 'description': 'Vibrant rainbow gradient on your display name', 'price': 40, 'icon': 'bi-rainbow'},
    {'key': 'gradient', 'name': 'Sunset Gradient', 'description': 'Warm orange-to-purple gradient text', 'price': 35, 'icon': 'bi-palette'},
    {'key': 'neon', 'name': 'Neon Glow', 'description': 'Bright neon cyan glow effect', 'price': 60, 'icon': 'bi-lightning-charge'},
    {'key': 'gold', 'name': 'Golden Shine', 'description': 'Luxurious metallic gold text', 'price': 80, 'icon': 'bi-gem'},
    {'key': 'ocean', 'name': 'Ocean Blue', 'description': 'Cool teal-to-blue flowing gradient', 'price': 45, 'icon': 'bi-water'},
    {'key': 'cursive', 'name': 'Elegant Script', 'description': 'Sophisticated cursive font style', 'price': 50, 'icon': 'bi-type'},
    {'key': 'fire', 'name': 'Fire Blaze', 'description': 'Red-orange flame gradient', 'price': 55, 'icon': 'bi-fire'},
]

def get_name_style_for_user(user_id):
    """Get the name_style for a user. Returns 'default' if none."""
    if not user_id:
        return 'default'
    try:
        p = UserProfile.query.filter_by(user_id=user_id, is_active=True).first()
        return (getattr(p, 'name_style', None) or 'default') if p else 'default'
    except Exception:
        return 'default'

def user_owns_shop_item(user_id, item_key):
    if not user_id or not item_key:
        return False
    return UserPurchase.query.filter_by(user_id=user_id, item_key=item_key).first() is not None

def _get_accounts_export_rows():
    """Build list of account rows for export (User + UserProfile joined)."""
    users = User.query.order_by(User.date_created.asc()).all()
    rows = []
    for u in users:
        profile = UserProfile.query.filter_by(user_id=u.id, is_active=True).first()
        rows.append({
            'User ID': u.id,
            'Username': u.username or '',
            'Email': u.email or '',
            'User Type (Account)': u.user_type or '',
            'Full Name': profile.name if profile else '',
            'User Type (Profile)': profile.user_type if profile else '',
            'Languages': profile.languages if profile else '',
            'Short Intro': (profile.short_intro or '')[:200] if profile else '',  # truncate long text
            'Interaction Type': profile.interaction_type if profile else '',
            'Meeting Style': profile.meeting_style if profile else '',
            'Interest Tags': profile.interest_tags if profile else '',
            'Total Points': profile.total_points if profile else 0,
            'Date Created': u.date_created.strftime('%Y-%m-%d %H:%M') if u.date_created else '',
            'Is Active': u.is_active,
        })
    return rows

def _update_accounts_export_file():
    """Write accounts export to exports/accounts_export.csv (updated when new accounts created)."""
    try:
        export_dir = os.path.join(basedir, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        path = os.path.join(export_dir, 'accounts_export.csv')
        rows = _get_accounts_export_rows()
        if not rows:
            return
        fieldnames = list(rows[0].keys())
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception:
        pass  # Don't block signup if export fails

@app.template_filter('photo_display_url')
def photo_display_url(photo_url):
    """Convert photo_url to full display URL. Handles external URLs and local uploads."""
    if not photo_url:
        return ''
    if photo_url.startswith('http://') or photo_url.startswith('https://'):
        return photo_url
    return url_for('static', filename='uploads/memories/' + photo_url)

@app.context_processor
def inject_auth():
    """Make auth data available in all templates."""
    user = get_logged_in_user()
    profile = get_logged_in_profile() if user else None
    notification_count = get_unread_notification_count(user.id) if user else 0
    current_name_style = (profile.name_style or 'default') if profile else 'default'
    return dict(
        current_user=user, current_profile=profile, notification_count=notification_count,
        current_name_style=current_name_style, get_name_style=get_name_style_for_user
    )

# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------

@app.route('/')
def home():
    return render_template('home.html')

# ---------------------------------------------------------
# AUTHENTICATION ROUTES (Signup, Login, Logout)
# ---------------------------------------------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        user_type = request.form.get('user_type', 'Youth')
        full_name = request.form.get('full_name', '').strip()
        languages = request.form.get('languages', '').strip()
        short_intro = request.form.get('short_intro', '').strip()
        
        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long.')
        if len(username) > 80:
            errors.append('Username must be 80 characters or less.')
        if not username.replace('_', '').replace('.', '').isalnum():
            errors.append('Username can only contain letters, numbers, underscores and dots.')
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            errors.append('Please enter a valid email address.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if not full_name or len(full_name) < 2:
            errors.append('Full name must be at least 2 characters long.')
        if user_type not in ('Youth', 'Senior'):
            errors.append('Please select a valid user type.')
        if not languages or len(languages.strip()) < 2:
            errors.append('Languages are required (at least 2 characters).')
        if not short_intro or len(short_intro.strip()) < 10:
            errors.append('Short introduction is required (at least 10 characters).')
        
        # Check uniqueness
        if User.query.filter_by(username=username).first():
            errors.append('Username is already taken.')
        if User.query.filter_by(email=email).first():
            errors.append('Email is already registered.')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('signup.html', 
                username=username, email=email, full_name=full_name,
                user_type=user_type, languages=languages, short_intro=short_intro)
        
        # Create User account
        new_user = User(
            username=username,
            email=email,
            user_type=user_type
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()  # Get the user ID
        
        # Create linked UserProfile
        new_profile = UserProfile(
            user_id=new_user.id,
            name=full_name,
            user_type=user_type,
            languages=languages,
            short_intro=short_intro,
            is_active=True
        )
        db.session.add(new_profile)
        db.session.flush()
        
        # Handle optional profile picture upload by file (same as Settings)
        pic_uploaded = False
        try:
            file = request.files.get('profile_picture')
            if file and file.filename and allowed_file(file.filename):
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                ext = file.filename.rsplit('.', 1)[1].lower()
                timestamp = int(datetime.utcnow().timestamp())
                filename = f"profile_{new_user.id}_{timestamp}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                new_profile.profile_picture_url = url_for('static', filename=f'uploads/profiles/{filename}')
                pic_uploaded = True
        except Exception:
            pass  # Don't block signup if upload fails
        
        db.session.commit()
        
        # Update accounts export file when new account is created
        _update_accounts_export_file()
        
        # Auto-login after signup
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        msg = f'Welcome to MasterCoders, {full_name}! Your account has been created.'
        if pic_uploaded:
            msg += ' Your profile picture has been uploaded.'
        flash(msg, 'success')
        return redirect(url_for('profile'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Validation
        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('login.html', username=username)
        
        # Find user by username or email
        user = User.query.filter(
            or_(User.username == username, User.email == username.lower())
        ).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid username or password.', 'danger')
            return render_template('login.html', username=username)
        
        if not user.is_active:
            flash('This account has been deactivated. Please contact support.', 'danger')
            return render_template('login.html', username=username)
        
        # Login successful
        session.clear()
        session['user_id'] = user.id
        session['username'] = user.username
        
        flash(f'Welcome back, {user.username}!', 'success')
        
        # Redirect to next page or home
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('home'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {username}! You have been logged out.', 'success')
    return redirect(url_for('login'))

# 1. READ: Display all posts
@app.route('/skills')
def skills_exchange():
    q = (request.args.get('q') or '').strip()

    selected_categories = request.args.getlist('category')
    if len(selected_categories) == 1 and ',' in selected_categories[0]:
        selected_categories = [c.strip() for c in selected_categories[0].split(',') if c.strip()]

    selected_skill_types = request.args.getlist('skill_type')
    if len(selected_skill_types) == 1 and ',' in selected_skill_types[0]:
        selected_skill_types = [s.strip() for s in selected_skill_types[0].split(',') if s.strip()]

    selected_user_types = request.args.getlist('user_type')
    if len(selected_user_types) == 1 and ',' in selected_user_types[0]:
        selected_user_types = [u.strip() for u in selected_user_types[0].split(',') if u.strip()]

    sort = (request.args.get('sort') or 'newest').strip()
    view = (request.args.get('view') or 'grid').strip()
    saved = (request.args.get('saved') or '').strip()  # client-side filter via localStorage

    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1

    try:
        per_page = int(request.args.get('per_page', 9))
    except ValueError:
        per_page = 9
    per_page = min(max(per_page, 6), 24)

    query = SkillPost.query

    if q:
        like = f"%{q}%"
        query = query.filter(or_(SkillPost.title.ilike(like), SkillPost.description.ilike(like)))

    if selected_categories:
        query = query.filter(SkillPost.category.in_(selected_categories))

    if selected_skill_types:
        query = query.filter(SkillPost.skill_type.in_(selected_skill_types))

    if selected_user_types:
        query = query.filter(SkillPost.user_type.in_(selected_user_types))

    if sort == 'oldest':
        query = query.order_by(SkillPost.date_posted.asc())
    elif sort == 'title':
        query = query.order_by(SkillPost.title.asc())
    else:
        query = query.order_by(SkillPost.date_posted.desc())

    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    if page > pages:
        page = pages

    posts = query.offset((page - 1) * per_page).limit(per_page).all()

    available_categories = [
        row[0]
        for row in db.session.query(SkillPost.category)
        .distinct()
        .order_by(SkillPost.category.asc())
        .all()
        if row[0]
    ]

    return render_template(
        'skills.html',
        posts=posts,
        q=q,
        sort=sort,
        view=view,
        saved=saved,
        page=page,
        pages=pages,
        per_page=per_page,
        total=total,
        available_categories=available_categories,
        selected_categories=selected_categories,
        selected_skill_types=selected_skill_types,
        selected_user_types=selected_user_types,
    )


@app.route('/skills/<int:post_id>')
def skill_detail(post_id: int):
    post = SkillPost.query.get(post_id)
    if not post:
        abort(404)
    return render_template('skill_detail.html', post=post)


@app.route('/skills/<int:post_id>/accept', methods=['GET'])
@login_required
def accept_skill_request(post_id: int):
    """Accept a skill request and redirect to chat with the requester."""
    post = SkillPost.query.get(post_id)
    if not post:
        abort(404)
    if post.skill_type != 'Request':
        flash('This is not a skill request.', 'warning')
        return redirect(url_for('skill_detail', post_id=post_id))
    if post.user_id == session.get('user_id'):
        flash("You can't accept your own request.", 'info')
        return redirect(url_for('skill_detail', post_id=post_id))
    
    partner_user_id = post.user_id
    if partner_user_id is None and post.author_name:
        name = (post.author_name or "").strip()
        if name:
            profile = UserProfile.query.filter(UserProfile.name == name).first()
            if profile:
                partner_user_id = profile.user_id
    
    if partner_user_id:
        return redirect(url_for('chat', partner_id=partner_user_id, source='skill', skill_post=post_id))
    
    if post.author_name:
        return redirect(url_for('chat', source='skill', author_name=post.author_name.strip()))
    
    flash("We couldn't connect you to the requester. They may need to link their account.", 'warning')
    return redirect(url_for('skill_detail', post_id=post_id))


@app.route('/skills/<int:post_id>/request-chat', methods=['GET'])
@login_required
def request_chat_skill_offer(post_id: int):
    """Request chat with someone who posted a skill offer (you want to accept their offer)."""
    post = SkillPost.query.get(post_id)
    if not post:
        abort(404)
    if post.skill_type != 'Offer':
        flash('This is not a skill offer.', 'warning')
        return redirect(url_for('skill_detail', post_id=post_id))
    if post.user_id == session.get('user_id'):
        flash("You can't chat with yourself.", 'info')
        return redirect(url_for('skill_detail', post_id=post_id))
    
    partner_user_id = post.user_id
    if partner_user_id is None and post.author_name:
        name = (post.author_name or "").strip()
        if name:
            profile = UserProfile.query.filter(UserProfile.name == name).first()
            if profile:
                partner_user_id = profile.user_id
    
    if partner_user_id:
        return redirect(url_for('chat', partner_id=partner_user_id, source='skill', from_offer=1, skill_post=post_id))
    
    if post.author_name:
        return redirect(url_for('chat', source='skill', author_name=post.author_name.strip(), from_offer=1))
    
    flash("We couldn't connect you to the offerer. They may need to link their account.", 'warning')
    return redirect(url_for('skill_detail', post_id=post_id))


# 3. UPDATE: Edit an existing post
@app.route('/skills/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_skill(post_id: int):
    post = SkillPost.query.get(post_id)
    if not post:
        abort(404)
    
    # Only the post author can edit
    if post.user_id != session.get('user_id'):
        flash('You can only edit your own posts.', 'danger')
        return redirect(url_for('skill_detail', post_id=post.id))
    
    # Get user profile
    profile = get_logged_in_profile()
    
    if request.method == 'POST':
        # Get data from form
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        skill_type = request.form.get('skill_type')

        # Automatically use profile data if available
        if profile:
            post.author_name = profile.name
            post.user_type = profile.user_type
            post.profile_picture_url = get_profile_picture_url(profile)

        # Validation
        if not title or len(title) < 3:
            flash('Title is too short!', 'danger')
            return render_template('edit_skill.html', post=post, profile=profile)
        
        # Update post
        post.title = title
        post.description = description
        post.category = category
        post.skill_type = skill_type
        
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('skill_detail', post_id=post.id))
    
    return render_template('edit_skill.html', post=post, profile=profile)

# 4. DELETE: Delete an existing post
@app.route('/skills/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_skill(post_id: int):
    post = SkillPost.query.get(post_id)
    if not post:
        abort(404)
    
    # Only the post author can delete
    if post.user_id != session.get('user_id'):
        flash('You can only delete your own posts.', 'danger')
        return redirect(url_for('skill_detail', post_id=post.id))
    
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('skills_exchange'))

# 2. CREATE: Add a new post
@app.route('/skills/new', methods=['GET', 'POST'])
@login_required
def create_skill():
    # Get user profile for auto-filling
    profile = get_logged_in_profile()
    
    if not profile:
        flash('Please complete your profile first to post skills.', 'warning')
        return redirect(url_for('profile_create'))
    
    if request.method == 'POST':
        # Get data from form
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        skill_type = request.form.get('skill_type')

        # Automatically use profile data
        author_name = profile.name
        user_type = profile.user_type
        profile_picture_url = get_profile_picture_url(profile)

        # Simple Validation
        if not title or len(title) < 3:
            flash('Title is too short!', 'danger')
            return render_template('create_skill.html', profile=profile)
        
        # Save to DB with profile data
        new_post = SkillPost(
            title=title,
            description=description,
            category=category,
            skill_type=skill_type,
            user_type=user_type,
            author_name=author_name,
            profile_picture_url=profile_picture_url,
            user_id=session.get('user_id')
        )
        db.session.add(new_post)
        
        # Award 10 points for creating a skill post
        if profile.total_points is None:
            profile.total_points = 0
        profile.total_points += 10
        
        db.session.commit()
        flash(f'Post created successfully! You earned 10 points! Total: {profile.total_points}', 'success')
        return redirect(url_for('skills_exchange'))

    return render_template('create_skill.html', profile=profile)

@app.route('/talk')
def talk():
    return render_template('talk.html')

@app.route('/messages')
def messages():
    return render_template('messages.html')

@app.route('/notifications')
@login_required
def notifications():
    """List user's notifications, optionally mark all as read."""
    user_id = session.get('user_id')
    if request.args.get('mark_read'):
        Notification.query.filter_by(user_id=user_id).update({'is_read': True})
        db.session.commit()
        return redirect(url_for('notifications'))
    notifs = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(50).all()
    return render_template('notifications.html', notifications=notifs)

def _chat_base_filter(my_id, partner_id, help_request_id=None, skill_post_id=None):
    """Base filter for chat messages - same post/context = same chat."""
    base = db.or_(
        db.and_(ChatMessage.sender_id == my_id, ChatMessage.receiver_id == partner_id),
        db.and_(ChatMessage.sender_id == partner_id, ChatMessage.receiver_id == my_id)
    )
    q = ChatMessage.query.filter(base)
    if help_request_id is not None:
        q = q.filter(ChatMessage.help_request_id == help_request_id)
    elif skill_post_id is not None:
        q = q.filter(ChatMessage.skill_post_id == skill_post_id)
    else:
        q = q.filter(ChatMessage.help_request_id.is_(None), ChatMessage.skill_post_id.is_(None))
    return q

@app.route('/api/chat/messages')
@login_required
def api_chat_messages():
    """Get chat messages between current user and partner (scoped by help_request or skill_post)."""
    partner_id = request.args.get('partner_id', type=int)
    help_request_id = request.args.get('help_request_id', type=int)
    skill_post_id = request.args.get('skill_post_id', type=int)
    if not partner_id:
        return jsonify([]), 400
    my_id = session.get('user_id')
    q = _chat_base_filter(my_id, partner_id, help_request_id or None, skill_post_id or None)
    messages = q.order_by(ChatMessage.created_at.asc()).all()
    return jsonify([{
        'id': m.id,
        'sender_id': m.sender_id,
        'receiver_id': m.receiver_id,
        'message': m.message,
        'created_at': m.created_at.isoformat() if m.created_at else None,
        'is_sent': m.sender_id == my_id
    } for m in messages])

@app.route('/api/chat/send', methods=['POST'])
@login_required
def api_chat_send():
    """Send a chat message (fallback when WebSocket not available)."""
    data = request.get_json() or {}
    partner_id = data.get('partner_id', type=int)
    text = (data.get('message') or '').strip()
    help_request_id = data.get('help_request_id', type=int)
    skill_post_id = data.get('skill_post_id', type=int)
    if not partner_id or not text or len(text) > 5000:
        return jsonify({'ok': False}), 400
    my_id = session.get('user_id')
    msg = ChatMessage(sender_id=my_id, receiver_id=partner_id, message=text,
                     help_request_id=help_request_id or None, skill_post_id=skill_post_id or None)
    db.session.add(msg)
    db.session.commit()
    # Notify receiver so they can reply on the same post
    sender_profile = UserProfile.query.filter_by(user_id=my_id).first()
    sender_name = sender_profile.name if sender_profile else "Someone"
    preview = text[:60] + ("..." if len(text) > 60 else "")
    if help_request_id:
        chat_url = url_for('chat', partner_id=my_id, help_request=help_request_id)
    elif skill_post_id:
        chat_url = url_for('chat', partner_id=my_id, source='skill', skill_post=skill_post_id)
    else:
        chat_url = url_for('chat', partner_id=my_id)
    create_notification(partner_id, 'chat_message', f'{sender_name} sent you a message', preview, chat_url)
    return jsonify({
        'ok': True,
        'id': msg.id,
        'created_at': msg.created_at.isoformat() if msg.created_at else None
    })

@app.route('/notifications/<int:notif_id>/read', methods=['POST', 'GET'])
@login_required
def mark_notification_read(notif_id):
    """Mark a single notification as read and redirect to its link (GET or POST)."""
    n = Notification.query.get_or_404(notif_id)
    if n.user_id != session.get('user_id'):
        abort(403)
    n.is_read = True
    db.session.commit()
    if n.link_url:
        return redirect(n.link_url)
    return redirect(url_for('notifications'))

@app.route('/bingo')
def bingo_storytelling():
    profile = get_logged_in_profile()
    return render_template('bingo_storytelling.html', profile=profile)

@app.route('/bingo/board')
def bingo_board():
    # Get all active prompts, limit to 9 for 3x3 grid
    all_prompts = BingoPrompt.query.filter_by(is_active=True).order_by(BingoPrompt.position).all()
    
    # If no prompts exist, create default ones (4x4 = 16 prompts) - Singapore themed
    if not all_prompts:
        default_prompts = [
            "Favourite National Day memory",
            "Most memorable hawker food you've eaten and where",
            "A Singapore slang or phrase you love using",
            "A place in Singapore you used to go a lot and how it changed",
            "Best school memory",
            "Your Singapore childhood snack",
            "Favourite MRT station name and why",
            "A moment you felt Singapore is very safe or steady",
            "A Singapore song you know by heart or can hum",
            "Your go-to kopitiam order",
            "First job or first allowance memory",
            "A kampung or old Singapore story",
            "Favourite Singapore holiday and what you do",
            "A Singapore habit you can't stop",
            "Favourite local TV show or actor",
            "A time you got lost in Singapore"
        ]
        for i, prompt_text in enumerate(default_prompts, 1):
            prompt = BingoPrompt(prompt_text=prompt_text, position=i)
            db.session.add(prompt)
        db.session.commit()
        all_prompts = BingoPrompt.query.filter_by(is_active=True).order_by(BingoPrompt.position).all()
    
    # Limit to first 16 prompts for 4x4 grid (or all if less than 16)
    prompts = all_prompts[:16] if len(all_prompts) >= 16 else all_prompts
    
    # Get THIS user's completed prompts only (per-account bingo board)
    user_id = session.get('user_id')
    if user_id:
        completed_prompt_ids = [story.prompt_id for story in BingoStory.query.filter_by(is_published=True, user_id=user_id).all()]
    else:
        completed_prompt_ids = []
    
    # Get recent stories for display (all users' stories are visible)
    recent_stories = BingoStory.query.filter_by(is_published=True).order_by(BingoStory.date_posted.desc()).limit(6).all()
    
    return render_template('bingo_board.html', prompts=prompts, completed_prompt_ids=completed_prompt_ids, recent_stories=recent_stories)

@app.route('/bingo/stories')
def bingo_stories():
    # Blog view - all published stories
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    stories = BingoStory.query.filter_by(is_published=True).order_by(BingoStory.date_posted.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('bingo_stories.html', stories=stories)

@app.route('/bingo/story/<int:story_id>')
def bingo_story_detail(story_id):
    try:
        story = BingoStory.query.get_or_404(story_id)
        prompt = BingoPrompt.query.get(story.prompt_id)
        comments = BingoComment.query.filter_by(story_id=story_id).order_by(BingoComment.date_posted.desc()).all()
        profile = get_logged_in_profile()
        user_has_liked = bool(session.get('user_id') and BingoStoryLike.query.filter_by(user_id=session['user_id'], story_id=story_id).first())
        return render_template('bingo_story_detail.html', story=story, prompt=prompt, comments=comments, profile=profile, user_has_liked=user_has_liked)
    except Exception as e:
        flash(f'Error loading story: {str(e)}', 'danger')
        return redirect(url_for('bingo_stories'))

@app.route('/bingo/create', methods=['GET', 'POST'])
@login_required
def bingo_create_story():
    # Get user profile for auto-filling
    profile = get_logged_in_profile()
    
    if not profile:
        flash('Please complete your profile first to write stories.', 'warning')
        return redirect(url_for('profile_create'))
    
    prompts = BingoPrompt.query.filter_by(is_active=True).order_by(BingoPrompt.position).all()
    selected_prompt_id = request.args.get('prompt_id', type=int)
    
    if request.method == 'POST':
        prompt_id = request.form.get('prompt_id')
        title = request.form.get('title', '').strip()
        story_content = request.form.get('story_content', '').strip()
        photo_url = None
        file = request.files.get('photo')
        if file and file.filename:
            ext = (file.filename.rsplit('.', 1)[-1] or '').lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = secure_filename(file.filename) or f"bingo_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
                file.save(os.path.join(app.config['MEMORY_UPLOAD_FOLDER'], filename))
                photo_url = filename  # Store filename; display uses uploads/memories/
        
        # Automatically use profile data
        author_name = profile.name
        user_type = profile.user_type
        
        # Validation
        if not prompt_id or not title or len(title) < 3:
            flash('Please provide a valid prompt and title (minimum 3 characters).', 'danger')
            return render_template('bingo_create_story.html', prompts=prompts, profile=profile)
        
        if not story_content or len(story_content) < 10:
            flash('Story content must be at least 10 characters long.', 'danger')
            return render_template('bingo_create_story.html', prompts=prompts, selected_prompt_id=selected_prompt_id, profile=profile)
        
        # Create story
        new_story = BingoStory(
            prompt_id=int(prompt_id),
            author_name=author_name,
            user_type=user_type,
            user_id=session.get('user_id'),
            title=title,
            story_content=story_content,
            photo_url=photo_url,
            points_earned=10  # Base points for posting
        )
        
        # Add 10 points to user's total points
        if profile.total_points is None:
            profile.total_points = 0
        profile.total_points += 10
        
        db.session.add(new_story)
        db.session.commit()
        
        flash(f'Story published successfully! You earned {new_story.points_earned} points! Total points: {profile.total_points}', 'success')
        return redirect(url_for('bingo_story_detail', story_id=new_story.id))
    
    return render_template('bingo_create_story.html', prompts=prompts, selected_prompt_id=selected_prompt_id, profile=profile)

@app.route('/bingo/story/<int:story_id>/edit', methods=['GET', 'POST'])
@login_required
def bingo_edit_story(story_id):
    story = BingoStory.query.get_or_404(story_id)
    if story.user_id is None or story.user_id != session.get('user_id'):
        flash('You can only edit your own stories.', 'danger')
        return redirect(url_for('bingo_story_detail', story_id=story_id))
    prompts = BingoPrompt.query.filter_by(is_active=True).order_by(BingoPrompt.position).all()
    
    if request.method == 'POST':
        story.prompt_id = int(request.form.get('prompt_id', story.prompt_id))
        story.title = request.form.get('title', story.title).strip()
        story.story_content = request.form.get('story_content', story.story_content).strip()
        file = request.files.get('photo')
        if file and file.filename:
            ext = (file.filename.rsplit('.', 1)[-1] or '').lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = secure_filename(file.filename) or f"bingo_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
                file.save(os.path.join(app.config['MEMORY_UPLOAD_FOLDER'], filename))
                story.photo_url = filename
        # If no new file uploaded, keep existing photo_url (already set on story)
        story.date_updated = datetime.utcnow()
        
        if len(story.title) < 3 or len(story.story_content) < 10:
            flash('Title must be at least 3 characters and story content at least 10 characters.', 'danger')
            profile = get_logged_in_profile()
            return render_template('bingo_edit_story.html', story=story, prompts=prompts, profile=profile)
        
        db.session.commit()
        flash('Story updated successfully!', 'success')
        return redirect(url_for('bingo_story_detail', story_id=story.id))
    
    profile = get_logged_in_profile()
    return render_template('bingo_edit_story.html', story=story, prompts=prompts, profile=profile)

@app.route('/bingo/story/<int:story_id>/delete', methods=['POST'])
@login_required
def bingo_delete_story(story_id):
    story = BingoStory.query.get_or_404(story_id)
    if story.user_id is None or story.user_id != session.get('user_id'):
        flash('You can only delete your own stories.', 'danger')
        return redirect(url_for('bingo_story_detail', story_id=story_id))
    db.session.delete(story)
    db.session.commit()
    flash('Story deleted successfully.', 'success')
    if request.form.get('next') == 'memory_album':
        return redirect(url_for('memory_album'))
    return redirect(url_for('bingo_stories'))

@app.route('/bingo/story/<int:story_id>/comment', methods=['POST'])
@login_required
def bingo_add_comment(story_id):
    story = BingoStory.query.get_or_404(story_id)
    
    # Get user profile for auto-filling
    profile = get_logged_in_profile()
    
    if not profile:
        flash('Please complete your profile first to comment.', 'warning')
        return redirect(url_for('profile_create'))
    
    # Automatically use profile data
    author_name = profile.name
    comment_text = request.form.get('comment_text', '').strip()
    
    if not comment_text or len(comment_text) < 3:
        flash('Comment must be at least 3 characters long.', 'danger')
        return redirect(url_for('bingo_story_detail', story_id=story_id))
    
    new_comment = BingoComment(
        story_id=story_id,
        author_name=author_name,
        user_id=session.get('user_id'),
        comment_text=comment_text,
        points_earned=2
    )
    
    # Add 2 points to user's total points
    if profile.total_points is None:
        profile.total_points = 0
    profile.total_points += 2
    
    story.comments_count += 1
    
    db.session.add(new_comment)
    db.session.commit()
    
    # Notify story owner if they're different from commenter
    if story.user_id and story.user_id != session.get('user_id'):
        create_notification(
            story.user_id, 'comment',
            'New comment on your story',
            f'{author_name} commented on "{story.title[:50]}{"..." if len(story.title) > 50 else ""}"',
            url_for('bingo_story_detail', story_id=story_id)
        )
    
    flash(f'Comment added! You earned 2 points! Total points: {profile.total_points}', 'success')
    return redirect(url_for('bingo_story_detail', story_id=story_id))

@app.route('/bingo/story/<int:story_id>/share', methods=['POST'])
@login_required
def bingo_share_story(story_id):
    """Award 5 points for copying/sharing story link. Returns JSON for AJAX or redirects for form."""
    story = BingoStory.query.get_or_404(story_id)
    profile = get_logged_in_profile()
    
    if not profile:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'Profile required'}), 400
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('profile_create'))
    
    # Award 5 points for sharing
    if profile.total_points is None:
        profile.total_points = 0
    profile.total_points += 5
    db.session.commit()
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'points': 5, 'total': profile.total_points})
    flash(f'Story shared! You earned 5 points! Total points: {profile.total_points}', 'success')
    return redirect(url_for('bingo_story_detail', story_id=story_id))

@app.route('/bingo/story/<int:story_id>/like', methods=['POST'])
@login_required
def bingo_like_story(story_id):
    """Like a story. Max 1 like per account."""
    story = BingoStory.query.get_or_404(story_id)
    user_id = session.get('user_id')
    if not user_id:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'Login required'}), 401
        flash('Please log in to like stories.', 'warning')
        return redirect(url_for('bingo_story_detail', story_id=story_id))
    existing = BingoStoryLike.query.filter_by(user_id=user_id, story_id=story_id).first()
    if existing:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'already_liked': True, 'likes': story.likes_count})
        flash('You have already liked this story.', 'info')
        return redirect(url_for('bingo_story_detail', story_id=story_id))
    like = BingoStoryLike(user_id=user_id, story_id=story_id)
    story.likes_count = (story.likes_count or 0) + 1
    db.session.add(like)
    db.session.commit()
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'likes': story.likes_count, 'liked': True})
    flash('Story liked!', 'success')
    return redirect(url_for('bingo_story_detail', story_id=story_id))

@app.route('/memory-album')
def memory_album():
    """Gallery of memories - WDP-style memory storytelling page."""
    memories = MemoryItem.query.order_by(MemoryItem.date_posted.desc()).all()
    return render_template('memory/gallery.html', memories=memories)

@app.route('/memory-album/upload', methods=['GET', 'POST'])
@login_required
def memory_upload():
    """Upload a new memory (title, caption, photo file)."""
    if request.method == 'POST':
        file = request.files.get('image')
        if not file or file.filename == '':
            flash('Please select a photo to upload.', 'warning')
            return redirect(url_for('memory_upload'))
        ext = (file.filename.rsplit('.', 1)[-1] or '').lower()
        if ext not in ALLOWED_EXTENSIONS:
            flash('Please upload a JPG, PNG, GIF or WebP image.', 'warning')
            return redirect(url_for('memory_upload'))
        filename = secure_filename(file.filename)
        if not filename:
            filename = f"memory_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
        file.save(os.path.join(app.config['MEMORY_UPLOAD_FOLDER'], filename))
        profile = get_logged_in_profile()
        uploader = profile.name if profile else (session.get('username') or 'Anonymous')
        memory = MemoryItem(
            title=request.form.get('title', '').strip() or 'Untitled',
            caption=request.form.get('caption', '').strip(),
            image_filename=filename,
            uploader=uploader,
            user_id=session.get('user_id')
        )
        db.session.add(memory)
        db.session.commit()
        flash('Memory published successfully!', 'success')
        return redirect(url_for('memory_album'))
    profile = get_logged_in_profile()
    return render_template('memory/upload.html', profile=profile)

@app.route('/memory-album/delete/<int:id>')
@login_required
def memory_delete(id):
    """Delete a memory (only owner can delete)."""
    memory = MemoryItem.query.get_or_404(id)
    if memory.user_id and memory.user_id != session.get('user_id'):
        flash('You can only delete your own memories.', 'danger')
        return redirect(url_for('memory_album'))
    db.session.delete(memory)
    db.session.commit()
    flash('Memory deleted.', 'success')
    return redirect(url_for('memory_album'))

@app.route('/bingo/shop')
@login_required
def bingo_shop():
    profile = get_logged_in_profile()
    if not profile:
        flash('Please create your profile first.', 'warning')
        return redirect(url_for('profile_create'))
    points = profile.total_points or 0
    owned = set()
    for p in UserPurchase.query.filter_by(user_id=session.get('user_id')).all():
        owned.add(p.item_key)
    return render_template('bingo_shop.html', items=BINGO_SHOP_ITEMS, points=points, owned=owned, profile=profile)

@app.route('/bingo/shop/purchase/<item_key>', methods=['POST'])
@login_required
def bingo_shop_purchase(item_key):
    profile = get_logged_in_profile()
    if not profile:
        flash('Please create your profile first.', 'warning')
        return redirect(url_for('profile_create'))
    item = next((i for i in BINGO_SHOP_ITEMS if i['key'] == item_key), None)
    if not item:
        flash('Invalid item.', 'danger')
        return redirect(url_for('bingo_shop'))
    if user_owns_shop_item(session.get('user_id'), item_key):
        flash('You already own this item.', 'info')
        return redirect(url_for('bingo_shop'))
    points = profile.total_points or 0
    if points < item['price']:
        flash(f'Not enough points. You need {item["price"]} pts, you have {points} pts.', 'danger')
        return redirect(url_for('bingo_shop'))
    profile.total_points = points - item['price']
    purchase = UserPurchase(user_id=session.get('user_id'), item_key=item_key)
    db.session.add(purchase)
    db.session.commit()
    flash(f'Purchased {item["name"]}! Equip it below.', 'success')
    return redirect(url_for('bingo_shop'))

@app.route('/bingo/shop/equip/<item_key>', methods=['POST'])
@login_required
def bingo_shop_equip(item_key):
    profile = get_logged_in_profile()
    if not profile:
        flash('Please create your profile first.', 'warning')
        return redirect(url_for('profile_create'))
    if item_key != 'default':
        item = next((i for i in BINGO_SHOP_ITEMS if i['key'] == item_key), None)
        if not item:
            flash('Invalid item.', 'danger')
            return redirect(url_for('bingo_shop'))
        if not user_owns_shop_item(session.get('user_id'), item_key):
            flash('You must purchase this item first.', 'danger')
            return redirect(url_for('bingo_shop'))
    profile.name_style = item_key
    db.session.commit()
    name = next((i['name'] for i in BINGO_SHOP_ITEMS if i['key'] == item_key), 'Default')
    if item_key == 'default':
        name = 'Default'
    flash(f'Equipped {name}! Your name will look great across the site.', 'success')
    return redirect(url_for('bingo_shop'))

@app.route('/leaderboard')
def leaderboard():
    # Get all profiles with points, ordered by total_points descending
    profiles = UserProfile.query.filter_by(is_active=True).order_by(
        UserProfile.total_points.desc()
    ).all()
    
    # Build leaderboard data with rank
    leaderboard_data = []
    for i, p in enumerate(profiles):
        points = p.total_points if p.total_points else 0
        # Count stories, comments, skill posts, and skills offered for this user
        story_count = BingoStory.query.filter_by(user_id=p.user_id, is_published=True).count() if p.user_id else 0
        comment_count = BingoComment.query.filter_by(user_id=p.user_id).count() if p.user_id else 0
        skill_count = SkillPost.query.filter_by(user_id=p.user_id).count() if p.user_id else 0
        skills_offered = SkillPost.query.filter_by(user_id=p.user_id, skill_type='Offer').count() if p.user_id else 0
        
        # Calculate helps given based on points: (total - stories*10 - comments*2 - skills*10) / 15
        # This is an approximation; we track it from points awarded
        helps_given = max(0, (points - story_count * 10 - comment_count * 2 - skill_count * 10) // 15)
        
        avatar_url = get_profile_picture_url(p)
        if p.profile_picture_url and p.date_updated:
            ts = int(p.date_updated.timestamp()) if hasattr(p.date_updated, 'timestamp') else 0
            avatar_url = f"{avatar_url}?v={ts}"
        name_style = getattr(p, 'name_style', None) or 'default'
        leaderboard_data.append({
            'rank': i + 1,
            'name': p.name,
            'name_style': name_style,
            'user_type': p.user_type,
            'total_points': points,
            'story_count': story_count,
            'comment_count': comment_count,
            'skills_offered': skills_offered,
            'helps_given': helps_given,
            'user_id': p.user_id,
            'avatar_url': avatar_url
        })
    
    # Get current user's rank
    current_user_rank = None
    user_id = session.get('user_id')
    if user_id:
        for entry in leaderboard_data:
            if entry['user_id'] == user_id:
                current_user_rank = entry['rank']
                break
    
    return render_template('leaderboard.html', leaderboard=leaderboard_data, current_user_rank=current_user_rank)

@app.route('/profile')
@login_required
def profile():
    profile = get_logged_in_profile()
    user = get_logged_in_user()
    
    # Get recent activities for this user
    recent_activities = SkillPost.query.filter_by(user_id=user.id).order_by(SkillPost.date_posted.desc()).limit(3).all() if profile else []
    
    return render_template('profile.html', profile=profile, recent_activities=recent_activities, datetime=datetime)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    profile = get_logged_in_profile()
    if not profile:
        flash('Profile not found. Please create a profile first.', 'info')
        return redirect(url_for('profile_create'))
    
    if request.method == 'POST':
        # Handle accessibility update via AJAX
        if request.form.get('update_accessibility'):
            setting = request.form.get('setting')
            value = request.form.get('value') == 'true'
            if setting == 'large_text':
                profile.large_text = value
            elif setting == 'high_contrast':
                profile.high_contrast = value
            elif setting == 'easy_reading':
                profile.easy_reading = value
            profile.date_updated = datetime.utcnow()
            db.session.commit()
            return {'status': 'success'}, 200
        
        # Full profile update
        profile.name = request.form.get('name', profile.name)
        profile.user_type = request.form.get('user_type', profile.user_type)
        profile.languages = request.form.get('languages', '')
        profile.short_intro = request.form.get('short_intro', '')
        profile.interaction_type = request.form.get('interaction_type', profile.interaction_type)
        profile.meeting_style = request.form.get('meeting_style', profile.meeting_style)
        profile.interest_tags = request.form.get('interest_tags', '')
        profile.large_text = request.form.get('large_text') == 'on'
        profile.high_contrast = request.form.get('high_contrast') == 'on'
        profile.easy_reading = request.form.get('easy_reading') == 'on'
        profile.date_updated = datetime.utcnow()
        
        # Handle profile picture upload
        file = request.files.get('profile_picture')
        if file and file.filename and allowed_file(file.filename):
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            ext = file.filename.rsplit('.', 1)[1].lower()
            # Unique filename to avoid browser caching old images
            timestamp = int(datetime.utcnow().timestamp())
            filename = f"profile_{profile.id}_{timestamp}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            profile.profile_picture_url = url_for('static', filename=f'uploads/profiles/{filename}')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile_edit.html', profile=profile)

@app.route('/profile/create', methods=['GET', 'POST'])
@login_required
def profile_create():
    user = get_logged_in_user()
    
    if request.method == 'POST':
        # Check if profile already exists for this user
        existing = UserProfile.query.filter_by(user_id=user.id, is_active=True).first()
        if existing:
            flash('Profile already exists. Please edit your existing profile.', 'info')
            return redirect(url_for('profile_edit'))
        
        # Check if there's an inactive profile for this user
        existing_inactive = UserProfile.query.filter_by(user_id=user.id, is_active=False).first()
        if existing_inactive:
            existing_inactive.is_active = True
            existing_inactive.name = request.form.get('name', '')
            existing_inactive.user_type = request.form.get('user_type', 'Youth')
            existing_inactive.languages = request.form.get('languages', '')
            existing_inactive.short_intro = request.form.get('short_intro', '')
            existing_inactive.interaction_type = request.form.get('interaction_type', '1-to-1')
            existing_inactive.meeting_style = request.form.get('meeting_style', 'Online')
            existing_inactive.interest_tags = request.form.get('interest_tags', '')
            existing_inactive.date_updated = datetime.utcnow()
            db.session.commit()
            flash('Profile reactivated and updated successfully!', 'success')
            return redirect(url_for('profile'))
        
        # Create new profile linked to this user
        new_profile = UserProfile(
            user_id=user.id,
            name=request.form.get('name', ''),
            user_type=request.form.get('user_type', 'Youth'),
            languages=request.form.get('languages', ''),
            short_intro=request.form.get('short_intro', ''),
            interaction_type=request.form.get('interaction_type', '1-to-1'),
            meeting_style=request.form.get('meeting_style', 'Online'),
            interest_tags=request.form.get('interest_tags', '')
        )
        
        db.session.add(new_profile)
        db.session.commit()
        _update_accounts_export_file()
        flash('Profile created successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile_create.html')

@app.route('/export-accounts')
@login_required
def export_accounts():
    """Export all account information to CSV (Excel-compatible). File updates automatically when new accounts are created."""
    rows = _get_accounts_export_rows()
    if not rows:
        flash('No accounts to export.', 'info')
        return redirect(url_for('profile'))
    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    filename = f'accounts_export_{datetime.utcnow().strftime("%Y%m%d_%H%M")}.csv'
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

@app.route('/profile/delete', methods=['POST'])
@login_required
def profile_delete():
    profile = get_logged_in_profile()
    if profile:
        profile.is_active = False
        profile.date_updated = datetime.utcnow()
        db.session.commit()
        flash('Profile deactivated successfully. You can create a new profile anytime.', 'success')
    else:
        flash('Profile not found', 'danger')
    return redirect(url_for('profile'))

# ================= JOURNAL ROUTES =================
def get_current_user():
    """Get current user's display name from session-based profile."""
    profile = get_logged_in_profile()
    return profile.name if profile else "Guest"

@app.route('/journal')
def journal_dashboard():
    entries = JournalEntry.query.order_by(JournalEntry.date_posted.desc()).all()
    current_user = get_current_user()
    return render_template('journal/dashboard.html', entries=entries, current_user=current_user)

@app.route('/journal/create', methods=['GET', 'POST'])
@login_required
def journal_create():
    if request.method == 'POST':
        tags = ",".join(request.form.getlist('tags'))
        current_user = get_current_user()
        entry = JournalEntry(
            title=request.form['title'],
            content=request.form['content'],
            mood=request.form['mood'],
            tags=tags,
            author=current_user
        )
        db.session.add(entry)
        db.session.commit()
        flash('Journal entry created successfully!', 'success')
        return redirect(url_for('journal_dashboard'))
    profile = get_logged_in_profile()
    return render_template('journal/form.html', entry=None, profile=profile)

@app.route('/journal/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def journal_edit(id):
    entry = JournalEntry.query.get_or_404(id)
    current_user = get_current_user()
    
    # Security Check: Prevent editing other people's posts
    if entry.author != current_user:
        flash('You can only edit your own entries.', 'danger')
        return redirect(url_for('journal_dashboard'))
        
    if request.method == 'POST':
        entry.title = request.form['title']
        entry.content = request.form['content']
        entry.mood = request.form['mood']
        entry.tags = ",".join(request.form.getlist('tags'))
        db.session.commit()
        flash('Journal entry updated successfully!', 'success')
        return redirect(url_for('journal_dashboard'))
    profile = get_logged_in_profile()
    return render_template('journal/form.html', entry=entry, profile=profile)

@app.route('/journal/delete/<int:id>')
@login_required
def journal_delete(id):
    entry = JournalEntry.query.get_or_404(id)
    current_user = get_current_user()
    
    # Security Check
    if entry.author == current_user:
        db.session.delete(entry)
        db.session.commit()
        flash('Journal entry deleted successfully!', 'success')
    else:
        flash('You can only delete your own entries.', 'danger')
    return redirect(url_for('journal_dashboard'))

@app.route('/journal/like/<int:id>')
@login_required
def journal_like(id):
    entry = JournalEntry.query.get_or_404(id)
    current_user = get_current_user()
    
    # Get current liked_by list
    liked_by_list = entry.liked_by.split(',') if entry.liked_by else []
    liked_by_list = [u for u in liked_by_list if u]  # Remove empty strings
    
    # Toggle like
    if current_user in liked_by_list:
        # Unlike
        entry.likes = max(0, entry.likes - 1)
        liked_by_list.remove(current_user)
    else:
        # Like
        entry.likes += 1
        liked_by_list.append(current_user)
    
    entry.liked_by = ','.join(liked_by_list)
    db.session.commit()
    return redirect(url_for('journal_dashboard'))

# ================= EVENT PLANNER ROUTES =================
@app.route('/events')
def events_list():
    events = Event.query.order_by(Event.date).all()
    organizer_names = {}
    for event in events:
        if event.organizer_name:
            organizer_names[event.id] = event.organizer_name
        elif event.user_id:
            profile = UserProfile.query.filter_by(user_id=event.user_id).first()
            organizer_names[event.id] = profile.name if profile else "Community Member"
        else:
            organizer_names[event.id] = "Community Member"
    return render_template('events/list.html', events=events, organizer_names=organizer_names)

@app.route('/events/create', methods=['GET', 'POST'])
@login_required
def event_create():
    profile = get_logged_in_profile()
    user = get_logged_in_user()
    poster_name = profile.name if profile else (user.username if user else "Community Member")
    if request.method == 'POST':
        event = Event(
            title=request.form['title'],
            description=request.form['description'],
            date=request.form['date'],
            time=request.form['time'],
            location=request.form['location'],
            capacity=int(request.form['capacity']),
            event_type=request.form['event_type'],
            organizer_name=poster_name,
            user_id=session.get('user_id')
        )
        db.session.add(event)
        db.session.commit()
        flash('Event created successfully!', 'success')
        return redirect(url_for('events_list'))
    return render_template('events/form.html', event=None, poster_name=poster_name, profile=profile)

@app.route('/events/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def event_edit(id):
    event = Event.query.get_or_404(id)
    if event.user_id != session.get('user_id'):
        flash('You can only edit your own events.', 'danger')
        return redirect(url_for('events_list'))
    if request.method == 'POST':
        profile = get_logged_in_profile()
        event.title = request.form['title']
        event.description = request.form['description']
        event.date = request.form['date']
        event.time = request.form['time']
        event.location = request.form['location']
        event.capacity = int(request.form['capacity'])
        event.event_type = request.form['event_type']
        if profile:
            event.organizer_name = profile.name
            event.user_id = session.get('user_id')
        db.session.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('events_list'))
    profile = get_logged_in_profile()
    user = get_logged_in_user()
    poster_name = profile.name if profile else (user.username if user else "Community Member")
    return render_template('events/form.html', event=event, poster_name=poster_name, profile=profile)

@app.route('/events/delete/<int:id>')
@login_required
def event_delete(id):
    event = Event.query.get_or_404(id)
    if event.user_id != session.get('user_id'):
        flash('You can only delete your own events.', 'danger')
        return redirect(url_for('events_list'))
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('events_list'))

# ================= COMMUNITY HELP APP ROUTES =================
# FAQ Data (read-only, curated)
FAQ_DATA = [
    {"id": 1, "priority": 1, "category": "Technology", "icon": "bi-laptop", "question": "How do I use WhatsApp to video call my grandchildren?", "answer": "Open WhatsApp, tap the contact (e.g. your grandchild), then tap the video camera icon at the top. Make sure you have allowed camera and microphone when the app asks. Stay in a well-lit area and use Wi‑Fi for a clearer call."},
    {"id": 2, "priority": 2, "category": "Technology", "icon": "bi-phone", "question": "How do I top up my prepaid mobile data?", "answer": "You can top up at any 7-Eleven, Cheers, or phone shop. Tell them your mobile number and say you want to add data or extend validity. You can also use the telco's app (e.g. Singtel Prepaid, StarHub prepaid) and pay with a debit or credit card."},
    {"id": 3, "priority": 3, "category": "Technology", "icon": "bi-bank", "question": "How do I use PayNow to send money?", "answer": "In your banking app, look for 'PayNow' or 'Transfer'. Enter the recipient's mobile number or NRIC. Type the amount and add a reference if you want. Double-check the name that appears, then confirm. The money is sent almost instantly."},
    {"id": 4, "priority": 4, "category": "Technology", "icon": "bi-wifi", "question": "My Wi-Fi at home keeps disconnecting. What can I check?", "answer": "• Restart your router: unplug for 30 seconds, then plug back in.\n• Move closer to the router if you are far away.\n• Make sure no large objects block the signal.\n• Call your internet provider if it still fails; they can run a line check."},
    {"id": 5, "priority": 5, "category": "Technology", "icon": "bi-shield-check", "question": "How do I know if a link or message is a scam?", "answer": "Be careful of messages asking you to click a link, verify your account, or claim a prize. Real banks and government agencies do not ask for passwords or OTPs by SMS link. If unsure, call the organisation using the number on their official website, not the number in the message."},
    {"id": 6, "priority": 6, "category": "Banking", "icon": "bi-credit-card", "question": "How do I activate my new ATM card?", "answer": "Most banks ask you to activate at an ATM: insert the card, enter the PIN mailed to you (or set one if prompted), and follow the screen. Some banks let you activate via their app or by calling their hotline. Keep the activation instructions that came with the card."},
    {"id": 7, "priority": 7, "category": "Banking", "icon": "bi-bank", "question": "Where can I find my bank's branch opening hours?", "answer": "Check your bank's website under 'Branch locator' or 'Contact us'. You can also call their hotline or use their mobile app. Some branches open on Saturday mornings; others are closed on weekends."},
    {"id": 8, "priority": 8, "category": "Banking", "icon": "bi-cash-stack", "question": "How do I check my CPF balance?", "answer": "Log in to the CPF website (cpf.gov.sg) with your Singpass. You can also use the CPF mobile app. If you have not used Singpass before, you may need to set it up at a Singpass counter or online with your NRIC."},
    {"id": 9, "priority": 9, "category": "Banking", "icon": "bi-receipt", "question": "I did not make a transaction but it appears on my statement. What should I do?", "answer": "Call your bank's hotline as soon as possible. Tell them the date, amount, and merchant. They will help you dispute the transaction and may freeze the card if needed. Always keep your card and PIN safe and never share OTPs."},
    {"id": 10, "priority": 10, "category": "Banking", "icon": "bi-piggy-bank", "question": "How do I set up a standing order or GIRO for bills?", "answer": "For utilities and some bills, you can apply for GIRO via the provider's form or website. For bank standing orders, go to your bank branch or use the app's 'Standing instruction' or 'Recurring transfer' option. You will need the payee's account details."},
    {"id": 11, "priority": 11, "category": "Transport", "icon": "bi-bus-front", "question": "How do I use the SimplyGo tap-and-go for buses and MRT?", "answer": "Use your contactless bank card, mobile wallet, or a SimplyGo-enabled card. Tap on when you board and tap off when you alight. For buses, tap once when boarding. Do not need to tap off. Fares are deducted automatically."},
    {"id": 12, "priority": 12, "category": "Transport", "icon": "bi-geo-alt", "question": "Which apps can I use to plan bus and MRT journeys?", "answer": "Google Maps, Citymapper, and the official 'Transport SG' (formerly MyTransport) app show bus and MRT routes, times, and fares. Enter your start and end point; the app suggests the best route and tells you which bus or train to take."},
    {"id": 13, "priority": 13, "category": "Transport", "icon": "bi-truck", "question": "How do I book a taxi or private-hire car?", "answer": "You can use apps like ComfortDelGro, Grab, or Gojek. Open the app, key in your pickup and drop-off address, and choose the type of ride. You can also call Comfort or other taxi companies. Some community centres help seniors book rides."},
    {"id": 14, "priority": 14, "category": "Transport", "icon": "bi-person-walking", "question": "I use a walking aid. Is public transport accessible?", "answer": "Most MRT stations have lifts and wide gates. Buses have priority seats and ramps or kneelers; drivers can lower the bus. Board when you are ready; you can ask for more time. The 'Transport SG' app can show accessible routes and facilities."},
    {"id": 15, "priority": 15, "category": "Transport", "icon": "bi-clock", "question": "Are there concession fares for seniors?", "answer": "Yes. If you are 60 or above, you can apply for a concession card or use your Passion Card for concession travel on buses and MRT. Apply at transit link offices, selected MRT stations, or online. Bring your NRIC and a recent photo."},
    {"id": 16, "priority": 16, "category": "Healthcare", "icon": "bi-heart-pulse", "question": "How do I make an appointment at a polyclinic?", "answer": "You can call the polyclinic, use the HealthHub app, or go to the polyclinic's website. First-time visitors may need to register with NRIC. If you have chronic conditions, ask about follow-up slots when you are there."},
    {"id": 17, "priority": 17, "category": "Healthcare", "icon": "bi-capsule", "question": "Where can I collect my medication if I miss the pick-up time?", "answer": "Polyclinics and hospitals usually let you collect within a few days. Call the pharmacy to confirm. Some hospitals have after-hours collection or can post to your address. Community centres sometimes arrange medicine delivery for seniors."},
    {"id": 18, "priority": 18, "category": "Healthcare", "icon": "bi-ambulance", "question": "When should I call 995 for an ambulance?", "answer": "Call 995 for emergencies: chest pain, severe difficulty breathing, sudden weakness on one side, serious injury, or if someone is unconscious. For non-urgent issues (e.g. stable fever, minor cuts), see a GP or use the 1777 non-emergency ambulance if available."},
    {"id": 19, "priority": 19, "category": "Healthcare", "icon": "bi-calendar-check", "question": "How do I use Medisave for my check-up or procedure?", "answer": "At the clinic or hospital, tell the staff you want to use Medisave. They will need your NRIC and may ask you to sign a form. There are withdrawal limits per procedure and per year; the staff can explain what you can use."},
    {"id": 20, "priority": 20, "category": "Healthcare", "icon": "bi-heart", "question": "How do I sign up for Healthier SG?", "answer": "Visit a participating clinic (GP or polyclinic) and enrol with your NRIC. You can also register via the HealthHub app or the Healthier SG website. Your doctor will help you set a care plan. There is no extra fee for enrolling."},
    {"id": 21, "priority": 21, "category": "Safety", "icon": "bi-shield-exclamation", "question": "Someone called and said they are from the bank or police. Is it safe?", "answer": "Scammers often pretend to be officials. Real banks and the police do not ask for your PIN, OTP, or to transfer money to 'safe accounts'. Hang up and call the organisation back using the number on their official website or your bank card."},
    {"id": 22, "priority": 22, "category": "Safety", "icon": "bi-key", "question": "How do I keep my Singpass and banking details safe?", "answer": "Never share your Singpass password or OTP with anyone. Do not click links in SMS or emails that ask you to log in. Use a strong, unique password and turn on two-factor authentication if offered. Log out after using shared computers."},
    {"id": 23, "priority": 23, "category": "Safety", "icon": "bi-house-door", "question": "Who can I call if I suspect a break-in or feel unsafe at home?", "answer": "Call the police at 999 for emergencies (e.g. break-in in progress, threat to safety). For general safety advice or to report something suspicious, you can call the nearest Neighbourhood Police Centre. Save these numbers in your phone."},
    {"id": 24, "priority": 24, "category": "Safety", "icon": "bi-telephone", "question": "How do I stop receiving scam or marketing calls?", "answer": "You can register with the Do Not Call (DNC) registry for marketing messages. For scam calls, do not answer unknown numbers when possible, or hang up without giving any info. Report scam numbers to the Singapore Police or via the ScamShield app."},
    {"id": 25, "priority": 25, "category": "Everyday Tips", "icon": "bi-lightbulb", "question": "Where can I get help with daily errands or heavy groceries?", "answer": "Ask at your Community Centre or CCC; they often have volunteers or programmes for seniors. You can also post a help request on this platform. Neighbours, family, or befriender services may be able to help with shopping or carrying items."},
    {"id": 26, "priority": 26, "category": "Everyday Tips", "icon": "bi-calendar-event", "question": "How do I join activities at the Community Centre?", "answer": "Visit your nearest CC or check the People's Association or OneService app for activities. Sign up in person or, for some courses, online. Many activities (e.g. exercise, karaoke, outings) are free or low-cost for seniors."},
    {"id": 27, "priority": 27, "category": "Everyday Tips", "icon": "bi-envelope", "question": "I have a lot of letters I don't understand. Who can explain them?", "answer": "Take them to your CC, CDC, or Social Service Office. Staff or volunteers can explain bills, government letters, or forms. You can also ask a trusted family member or neighbour. Do not give originals to strangers; use copies if someone offers to 'help' outside official places."},
    {"id": 28, "priority": 28, "category": "Everyday Tips", "icon": "bi-people", "question": "Where can I find company or someone to talk to?", "answer": "Senior activity centres, Wellness Centres, and CCs run group activities and social sessions. Silver Generation Office and AIC can point you to befriending services. You can also use this platform to connect with others or ask for a chat buddy."},
    {"id": 29, "priority": 29, "category": "Everyday Tips", "icon": "bi-question-circle", "question": "Who helps with utilities or conservancy rebates and vouchers?", "answer": "CDC vouchers and U-Save rebates are usually explained in the mail or on the relevant government website. If you are unsure, go to your CC or SSO with the letter and your NRIC. Staff can help you understand or apply for schemes you qualify for."},
    {"id": 30, "priority": 30, "category": "Safety", "icon": "bi-exclamation-triangle", "question": "What should I do if I think I have been scammed?", "answer": "Call your bank immediately to freeze your accounts or cards. Report to the Police (999 if urgent, or visit a NPC). Keep records of messages, emails, and receipts. Do not delete evidence. Report to the Anti-Scam Helpline (1800-722-6688) for advice."},
]

FAQ_CATEGORIES = ["All", "Technology", "Banking", "Transport", "Healthcare", "Safety", "Everyday Tips"]
PER_PAGE = 10

# Topic data (in-memory)
TOPICS = {
    1: {"title": "Tea & Coffee Moments", "icon": "🍵"},
    2: {"title": "Neighbourhood Memories", "icon": "🏘️"},
    3: {"title": "Festivals & Traditions", "icon": "🎭"},
    4: {"title": "Food & Hawker Culture", "icon": "🍜"},
    5: {"title": "Music & Old Songs", "icon": "🎵"},
    6: {"title": "Growing Older Gracefully", "icon": "📚"},
    7: {"title": "Travel & Adventures", "icon": "✈️"},
    8: {"title": "Family & Grandchildren", "icon": "👨‍👩‍👧‍👦"},
    9: {"title": "Life Experiences", "icon": "🌿"},
    10: {"title": "Sports & Games", "icon": "⚽"},
}

topic_interest = {}
_next_user_topic_id = 11

TOPIC_PEOPLE = {
    1: [{"id": "raj", "name": "Raj", "avatar_url": "/static/avatar.svg", "short_bio": "Kopi enthusiast and former small-business owner.", "topic_id": 1}, {"id": "1_2", "name": "Wei Ming", "avatar_url": "/static/avatar.svg", "short_bio": "Loves teh tarik and hawker kopi culture.", "topic_id": 1}, {"id": "1_3", "name": "Susan", "avatar_url": "/static/avatar.svg", "short_bio": "Morning coffee rituals and chat with neighbours.", "topic_id": 1}],
    2: [{"id": "2_1", "name": "Kumar", "avatar_url": "/static/avatar.svg", "short_bio": "Grew up in a kampung; shares old estate stories.", "topic_id": 2}, {"id": "2_2", "name": "Lily", "avatar_url": "/static/avatar.svg", "short_bio": "HDB memories and void deck gatherings.", "topic_id": 2}, {"id": "2_3", "name": "David", "avatar_url": "/static/avatar.svg", "short_bio": "Neighbourhood shops and familiar faces.", "topic_id": 2}],
    3: [{"id": "ahmad", "name": "Ahmad", "avatar_url": "/static/avatar.svg", "short_bio": "Enjoys sharing about Hari Raya and family traditions.", "topic_id": 3}, {"id": "3_2", "name": "Pei Ling", "avatar_url": "/static/avatar.svg", "short_bio": "CNY, Mid-Autumn and family reunions.", "topic_id": 3}, {"id": "3_3", "name": "Priya", "avatar_url": "/static/avatar.svg", "short_bio": "Deepavali, Thaipusam and temple visits.", "topic_id": 3}],
    4: [{"id": "mei", "name": "Mei Lin", "avatar_url": "/static/avatar.svg", "short_bio": "Loves cooking and hawker stories. Grandmother of three.", "topic_id": 4}, {"id": "4_2", "name": "Uncle Tan", "avatar_url": "/static/avatar.svg", "short_bio": "Roti prata, chicken rice, and family recipes.", "topic_id": 4}, {"id": "4_3", "name": "Nurul", "avatar_url": "/static/avatar.svg", "short_bio": "Malay and Peranakan food traditions.", "topic_id": 4}],
    5: [{"id": "5_1", "name": "Ah Seng", "avatar_url": "/static/avatar.svg", "short_bio": "Xinyao and 80s Mandopop.", "topic_id": 5}, {"id": "5_2", "name": "Maria", "avatar_url": "/static/avatar.svg", "short_bio": "Oldies, karaoke and community concerts.", "topic_id": 5}, {"id": "5_3", "name": "Ravi", "avatar_url": "/static/avatar.svg", "short_bio": "Classical Indian and Bollywood favourites.", "topic_id": 5}],
    6: [{"id": "6_1", "name": "Auntie Lim", "avatar_url": "/static/avatar.svg", "short_bio": "Tai chi, gardening and staying active.", "topic_id": 6}, {"id": "6_2", "name": "Hassan", "avatar_url": "/static/avatar.svg", "short_bio": "Reading, grandkids and simple pleasures.", "topic_id": 6}, {"id": "6_3", "name": "Grace", "avatar_url": "/static/avatar.svg", "short_bio": "Volunteering and lifelong learning.", "topic_id": 6}],
    7: [{"id": "7_1", "name": "John", "avatar_url": "/static/avatar.svg", "short_bio": "Backpacking in the 70s and 80s.", "topic_id": 7}, {"id": "7_2", "name": "Siew Lee", "avatar_url": "/static/avatar.svg", "short_bio": "Family trips and favourite destinations.", "topic_id": 7}, {"id": "7_3", "name": "Ramesh", "avatar_url": "/static/avatar.svg", "short_bio": "Pilgrimages and cultural tours.", "topic_id": 7}],
    8: [{"id": "siti", "name": "Siti", "avatar_url": "/static/avatar.svg", "short_bio": "Retired teacher, passionate about family and grandkids.", "topic_id": 8}, {"id": "8_2", "name": "Robert", "avatar_url": "/static/avatar.svg", "short_bio": "Grandfather of five; weekend gatherings.", "topic_id": 8}, {"id": "8_3", "name": "Mdm Wong", "avatar_url": "/static/avatar.svg", "short_bio": "Raising kids in the 80s and 90s.", "topic_id": 8}],
    9: [{"id": "9_1", "name": "Uncle Ho", "avatar_url": "/static/avatar.svg", "short_bio": "Lessons from work and family life.", "topic_id": 9}, {"id": "9_2", "name": "Aisha", "avatar_url": "/static/avatar.svg", "short_bio": "Milestones, gratitude and everyday wisdom.", "topic_id": 9}, {"id": "9_3", "name": "James", "avatar_url": "/static/avatar.svg", "short_bio": "Retirement, hobbies and new chapters.", "topic_id": 9}],
    10: [{"id": "10_1", "name": "Uncle Tan", "avatar_url": "/static/avatar.svg", "short_bio": "Community football and morning jogging.", "topic_id": 10}, {"id": "10_2", "name": "Auntie Lee", "avatar_url": "/static/avatar.svg", "short_bio": "Table tennis and badminton at the CC.", "topic_id": 10}, {"id": "10_3", "name": "Rahim", "avatar_url": "/static/avatar.svg", "short_bio": "Catch and sepak takraw with the neighbours.", "topic_id": 10}],
}

CHAT_CONTENT = {
    "Tea & Coffee Moments": {"opening_message": "Hi there! Nice to connect over tea and coffee talk ☕", "suggested_points": ["Do you prefer kopi or teh?", "Any favourite coffee shops near you?", "How was kopi different in the past?", "Who do you usually drink coffee with?"]},
    "Neighbourhood Memories": {"opening_message": "Hello! I'd love to hear about the neighbourhoods you've known 🏘️", "suggested_points": ["What's your favourite memory of where you grew up?", "How has your area changed over the years?", "Any shops or places you still miss?", "What made your neighbourhood feel like home?"]},
    "Festivals & Traditions": {"opening_message": "Hello! I'd love to hear about the festivals you celebrate 🎉", "suggested_points": ["Which festival do you enjoy the most?", "How did your family celebrate in the past?", "Any special traditions you still keep?", "What festival food do you miss most?"]},
    "Food & Hawker Culture": {"opening_message": "Hi! I'm always keen to talk about food and hawker culture 🍜", "suggested_points": ["What's your go-to hawker dish?", "Any family recipes you still make?", "How has hawker food changed over the years?", "Where do you like to eat with family or friends?"]},
    "Music & Old Songs": {"opening_message": "Hi! Let's chat about music and the songs that matter to you 🎵", "suggested_points": ["Which songs bring back the strongest memories?", "Do you still listen to the same genres as before?", "Any concerts or performances you'll never forget?", "What music did your family play when you were young?"]},
    "Growing Older Gracefully": {"opening_message": "Hi! It's nice to chat about staying positive and active 🌱", "suggested_points": ["What keeps you active these days?", "Any hobbies you picked up later in life?", "What advice would you give your younger self?", "How do you stay positive day to day?"]},
    "Travel & Adventures": {"opening_message": "Hello! I'd enjoy hearing about your travels and adventures ✈️", "suggested_points": ["What's the most memorable trip you've taken?", "Any place you've always wanted to go?", "How did travel used to be different?", "Who do you like to travel with?"]},
    "Family & Grandchildren": {"opening_message": "Hi! I'd love to hear about your family and the people close to you 👨‍👩‍👧‍👦", "suggested_points": ["What do you enjoy most about time with family?", "Any traditions you've passed on to the next generation?", "How has family life changed over the years?", "What do you like to do with your grandchildren?"]},
    "Life Experiences": {"opening_message": "Hello! I'm glad we can share a bit about life and what we've learned 🌿", "suggested_points": ["What's one thing you're grateful for?", "Any lesson you'd pass on to others?", "How do you like to spend your time now?", "What milestone are you most proud of?"]},
    "Sports & Games": {"opening_message": "Hi! Great to chat about sports and games — what do you enjoy playing or watching? ⚽", "suggested_points": ["What sports or games do you like to play or watch?", "Any favourite memories from community games or matches?", "How do you stay active these days?", "Do you follow any local or international teams?"]},
}

CHAT_CONTENT_FALLBACK = {"opening_message": "Hi! Great to chat with you — I'd love to hear what's on your mind 🙂", "suggested_points": ["What would you like to talk about?", "I'd love to hear your story", "Anything on your mind lately?", "How has your week been?"]}

TOPIC_DESCRIPTIONS = {
    1: "Share stories over tea and coffee.",
    2: "Stories from your neighbourhood and community.",
    3: "Celebrations and cultural traditions.",
    4: "Hawker food, recipes and food memories.",
    5: "Favourite songs and music from the past.",
    6: "Staying active and positive in later years.",
    7: "Trips, travels and adventures.",
    8: "Family life and time with grandchildren.",
    9: "Lessons and stories from life.",
    10: "Sports, games and staying active.",
}

SEEDED_TOPIC_IDS = set(TOPICS.keys())
SEEDED_INTEREST = {1: 12, 2: 15, 3: 31, 4: 42, 5: 18, 6: 22, 7: 14, 8: 36, 9: 20, 10: 25}
DEFAULT_CONVERSATION_ICON = "💬"

def _add_column_if_missing(cursor, table, column, col_type):
    """Add column to table if it doesn't exist (SQLite)."""
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

def ensure_help_offers_table():
    """Create help_offers table if it doesn't exist and add user_id if missing."""
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS help_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            help_request_id INTEGER,
            offer_text TEXT,
            availability TEXT,
            help_mode TEXT
        )
    """)
    _add_column_if_missing(cursor, "help_offers", "user_id", "INTEGER")
    conn.commit()
    conn.close()

def ensure_help_requests_table():
    """Create help_requests table if it doesn't exist and seed default requests."""
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS help_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT,
            preferred_help_method TEXT,
            mode TEXT,
            time_needed TEXT,
            urgency TEXT,
            posted_by TEXT,
            time_ago TEXT,
            status TEXT DEFAULT 'Open'
        )
    """)
    
    # Check if table already has data
    cursor.execute("SELECT COUNT(*) FROM help_requests")
    count = cursor.fetchone()[0]
    
    # Seed 18 default help requests if table is empty
    if count == 0:
        default_requests = [
            ("Help setting up WhatsApp", "Need help setting up WhatsApp on my phone. I'm not sure how to add contacts or send messages.", "Technology", "Online", "Online", "30 mins", "Normal", "Mdm Tan", "2 hours ago"),
            ("Grocery shopping assistance", "Need help buying groceries at NTUC. I have difficulty carrying heavy items.", "Shopping", "Meetup", "Meetup", "1 hour", "Urgent", "Uncle Lim", "5 hours ago"),
            ("Fix WiFi connection", "My home WiFi keeps disconnecting. I need someone to check my router settings.", "Technology", "Meetup", "Meetup", "1–2 hours", "Normal", "Mr Goh", "1 day ago"),
            ("Book polyclinic appointment", "Need help booking a medical appointment online. The website is confusing.", "Health", "Online", "Online", "30 mins", "Urgent", "Auntie Mary", "3 hours ago"),
            ("Help using Zoom", "Not sure how to join Zoom calls. My daughter wants me to join family video calls.", "Technology", "Online", "Online", "45 mins", "Normal", "Mr Ong", "1 day ago"),
            ("Transportation to clinic", "Need a ride to the polyclinic next week for my check-up. Public transport is difficult for me.", "Transportation", "Meetup", "Meetup", "2 hours", "Normal", "Auntie Siti", "4 hours ago"),
            ("Read mail and bills", "Need help reading and understanding my utility bills. The text is too small.", "Administrative", "Meetup", "Meetup", "30 mins", "Normal", "Uncle Raj", "6 hours ago"),
            ("Set up mobile banking", "Want to learn how to use mobile banking app. Need step-by-step guidance.", "Technology", "Online", "Online", "1 hour", "Normal", "Mdm Lee", "1 day ago"),
            ("Garden maintenance", "Need help trimming plants in my garden. I can't reach the high branches.", "Home & Garden", "Meetup", "Meetup", "2–3 hours", "Normal", "Mr Chua", "2 days ago"),
            ("Learn to use smartphone", "Just got a new smartphone. Need basic lessons on how to use it.", "Technology", "Meetup", "Meetup", "1–2 hours", "Normal", "Auntie Kim", "1 day ago"),
            ("Help with online shopping", "Want to buy something online but don't know how. Need guidance on using shopping websites.", "Shopping", "Online", "Online", "45 mins", "Normal", "Mdm Wong", "3 hours ago"),
            ("Fix leaking tap", "Kitchen tap is leaking. Need someone to help fix it or recommend a plumber.", "Home & Garden", "Meetup", "Meetup", "1 hour", "Urgent", "Uncle Tan", "1 hour ago"),
            ("Fill out government forms", "Need help filling out a government form. The instructions are unclear.", "Administrative", "Meetup", "Meetup", "45 mins", "Normal", "Mr Lim", "5 hours ago"),
            ("Learn to use email", "Want to send emails to my grandchildren. Need to learn how to create and send emails.", "Technology", "Online", "Online", "1 hour", "Normal", "Auntie Lim", "2 days ago"),
            ("Grocery delivery setup", "Want to order groceries online for delivery. Need help setting up an account.", "Shopping", "Online", "Online", "30 mins", "Normal", "Mdm Chen", "4 hours ago"),
            ("Help with medication", "Need help organizing my weekly medication. Too many pills to keep track of.", "Health", "Meetup", "Meetup", "30 mins", "Normal", "Uncle Koh", "6 hours ago"),
            ("Fix computer slow", "My computer is very slow. Need someone to check what's wrong and help speed it up.", "Technology", "Meetup", "Meetup", "1–2 hours", "Normal", "Mr Teo", "1 day ago"),
            ("Learn to use video calls", "Want to video call my family overseas. Need help learning how to use video calling apps.", "Technology", "Online", "Online", "45 mins", "Normal", "Auntie Ng", "3 hours ago"),
        ]
        
        cursor.executemany("""
            INSERT INTO help_requests 
            (title, description, category, preferred_help_method, mode, time_needed, urgency, posted_by, time_ago, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open')
        """, default_requests)
        conn.commit()
    
    _add_column_if_missing(cursor, "help_requests", "user_id", "INTEGER")
    _add_column_if_missing(cursor, "help_requests", "accepted_offer_id", "INTEGER")
    conn.commit()
    conn.close()

def ensure_topics_table():
    """Create topics table if it doesn't exist."""
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            category TEXT
        )
    """)
    # Seed initial topics if they don't exist
    for topic_id, topic_data in TOPICS.items():
        cursor.execute("SELECT id FROM topics WHERE id = ?", (topic_id,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO topics (id, title, description, category) VALUES (?, ?, ?, ?)",
                (topic_id, topic_data["title"], TOPIC_DESCRIPTIONS.get(topic_id, ""), "")
            )
    conn.commit()
    conn.close()

def _canonical_topic(s):
    """Normalise topic string for matching: lowercase, trimmed."""
    if not s or not isinstance(s, str):
        return ""
    return s.strip().lower()

def _resolve_topic_param(topic_param):
    """Resolve topic query param to (topic_id, topic)."""
    s = (topic_param.strip() if topic_param and isinstance(topic_param, str) else "") or ""
    canon = _canonical_topic(s)
    if not canon or canon == "random":
        return None
    if canon == "sports & games":
        return (10, TOPICS[10])
    for tid, t in TOPICS.items():
        if _canonical_topic(t.get("title") or "") == canon:
            return tid, TOPICS[tid]
    return None

# Initialize database tables
ensure_help_requests_table()
ensure_help_offers_table()
ensure_topics_table()


@app.route('/help')
def help_requests():
    search_query = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "").strip()
    
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    where_conditions = []
    params = []
    
    if search_query:
        where_conditions.append("(title LIKE ? OR description LIKE ?)")
        search_pattern = f"%{search_query}%"
        params.extend([search_pattern, search_pattern])
    
    if category_filter:
        where_conditions.append("category = ?")
        params.append(category_filter)
    
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    query = f"SELECT * FROM help_requests WHERE {where_clause} ORDER BY id DESC"
    cursor.execute(query, params)
    requests = cursor.fetchall()
    
    processed_requests = []
    for req in requests:
        req_dict = dict(req)
        req_dict['mode'] = req_dict.get('preferred_help_method', '')
        req_dict['urgency'] = req_dict.get('urgency', 'Normal')
        req_dict['posted_by'] = req_dict.get('posted_by', 'Community Member')
        req_dict['time_ago'] = req_dict.get('time_ago', 'recently')
        req_dict['time_needed'] = req_dict.get('time_needed', '')
        processed_requests.append(req_dict)
    
    conn.close()
    
    return render_template("help_requests.html", help_requests=processed_requests)

@app.route('/help/<int:request_id>')
def help_detail(request_id):
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM help_requests WHERE id = ?", (request_id,))
    help_request = cursor.fetchone()
    if help_request is None:
        conn.close()
        return "Help request not found", 404
    
    # Fetch offers for this request
    cursor.execute(
        "SELECT id, help_request_id, offer_text, availability, help_mode, user_id FROM help_offers WHERE help_request_id = ? ORDER BY id DESC",
        (request_id,)
    )
    offers = [dict(row) for row in cursor.fetchall()]
    # Map help_mode to help_method for template
    for o in offers:
        o['help_method'] = o.get('help_mode', '—')
    conn.close()
    
    # Only the request author can accept offers
    help_req_dict = dict(help_request)
    req_user_id = help_req_dict.get('user_id')
    current_user_id = session.get('user_id')
    is_request_owner = bool(current_user_id and req_user_id is not None and current_user_id == req_user_id)
    
    # For resolved requests with an accepted offer, get helper's user_id for "Chat with helper" link
    accepted_offer_user_id = None
    if help_req_dict.get("status") == "Resolved" and help_req_dict.get("accepted_offer_id"):
        for o in offers:
            if o.get("id") == help_req_dict.get("accepted_offer_id"):
                accepted_offer_user_id = o.get("user_id")
                break
    
    return render_template(
        "help_detail.html",
        help_request=help_req_dict,
        offers=offers,
        is_request_owner=is_request_owner,
        accepted_offer_user_id=accepted_offer_user_id,
        resolved=request.args.get("resolved")
    )

@app.route('/help/<int:id>/offer', methods=["POST"])
@login_required
def submit_offer(id):
    ensure_help_offers_table()
    
    offer_message = request.form.get("offer_text", "")
    availability_option = request.form.get("availability", "")
    preferred_help_method = request.form.get("help_mode", "")
    user_id = session.get("user_id")
    
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, title FROM help_requests WHERE id = ?", (id,))
    help_req = cursor.fetchone()
    cursor.execute(
        "INSERT INTO help_offers (help_request_id, offer_text, availability, help_mode, user_id) VALUES (?, ?, ?, ?, ?)",
        (id, offer_message, availability_option, preferred_help_method, user_id)
    )
    conn.commit()
    req_user_id = help_req["user_id"] if help_req and help_req["user_id"] else None
    req_title = "Your request"
    if help_req and help_req["title"]:
        req_title = help_req["title"][:50] + ("..." if len(help_req["title"]) > 50 else "")
    conn.close()
    
    # Notify request owner (don't notify self)
    if req_user_id and req_user_id != user_id:
        offerer_profile = get_logged_in_profile()
        offerer_name = offerer_profile.name if offerer_profile else "Someone"
        create_notification(
            req_user_id, 'help_offer',
            'New help offer on your request',
            f'{offerer_name} offered to help with "{req_title}"',
            url_for('help_detail', request_id=id)
        )
    
    flash('Offer submitted successfully! You will earn 15 points when your offer is accepted.', 'success')
    return redirect(url_for("help_detail", request_id=id, offer_sent=1))

@app.route('/help/<int:request_id>/accept/<int:offer_id>', methods=["POST"])
@login_required
def accept_offer(request_id, offer_id):
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, status FROM help_requests WHERE id = ?", (request_id,))
    help_request = cursor.fetchone()
    if not help_request:
        conn.close()
        return "Help request not found", 404
    req_dict = dict(help_request)
    req_user_id = req_dict.get("user_id")
    current_uid = session.get("user_id")
    if req_user_id is None or current_uid is None or req_user_id != current_uid:
        conn.close()
        flash("Only the person who posted this request can accept offers.", "danger")
        return redirect(url_for("help_detail", request_id=request_id))
    if req_dict.get("status") == "Resolved":
        conn.close()
        flash("This request has already been resolved.", "warning")
        return redirect(url_for("help_detail", request_id=request_id))
    
    cursor.execute("SELECT id, user_id FROM help_offers WHERE id = ? AND help_request_id = ?", (offer_id, request_id))
    offer = cursor.fetchone()
    if not offer:
        conn.close()
        flash("Offer not found.", "danger")
        return redirect(url_for("help_detail", request_id=request_id))
    
    cursor.execute(
        "UPDATE help_requests SET status = ?, accepted_offer_id = ? WHERE id = ?",
        ("Resolved", offer_id, request_id)
    )
    cursor.execute("SELECT title FROM help_requests WHERE id = ?", (request_id,))
    req_row = cursor.fetchone()
    req_title = (req_row["title"][:50] + "...") if req_row and req_row["title"] and len(req_row["title"]) > 50 else (req_row["title"] or "Help request") if req_row else "Help request"
    conn.commit()
    conn.close()
    
    helper_user_id = offer["user_id"] if offer["user_id"] is not None else None
    
    # Notify helper that their offer was accepted
    if helper_user_id:
        requester_profile = UserProfile.query.filter_by(user_id=req_user_id).first()
        requester_name = requester_profile.name if requester_profile else "Someone"
        create_notification(
            helper_user_id, 'offer_accepted',
            'Your offer was accepted!',
            f'{requester_name} accepted your offer to help with "{req_title}"',
            url_for('chat', partner_id=req_user_id, help_request=request_id)
        )
    
    # Award 15 points to the helper whose offer was accepted
    if helper_user_id:
        profile = UserProfile.query.filter_by(user_id=helper_user_id).first()
        if profile:
            if profile.total_points is None:
                profile.total_points = 0
            profile.total_points += 15
            db.session.commit()
            flash("Offer accepted! The helper earned 15 points. You can chat with them below to arrange the details.", "success")
    else:
        flash("Offer accepted successfully! You can chat with them below to arrange the details.", "success")
    
    # Link to chat with the helper
    if helper_user_id:
        return redirect(url_for("chat", partner_id=helper_user_id, help_request=request_id))
    return redirect(url_for("help_detail", request_id=request_id, resolved=1))

@app.route('/help/<int:request_id>/resolve', methods=["POST"])
@login_required
def resolve_help_request(request_id):
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id FROM help_requests WHERE id = ?", (request_id,))
    help_request = cursor.fetchone()
    conn.close()
    if not help_request:
        return "Help request not found", 404
    # Only the request author can mark as resolved
    req_user_id = help_request["user_id"] if hasattr(help_request, "keys") else help_request[1]
    if req_user_id != session.get("user_id"):
        flash("Only the person who posted this request can mark it as resolved.", "danger")
        return redirect(url_for("help_detail", request_id=request_id))
    
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    cursor = conn.cursor()
    cursor.execute("UPDATE help_requests SET status = ? WHERE id = ?", ("Resolved", request_id))
    conn.commit()
    conn.close()
    flash("Help request marked as resolved.", "success")
    return redirect(url_for("help_detail", request_id=request_id, resolved=1))

@app.route('/help/create', methods=['GET', 'POST'])
@login_required
def create_help():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        preferred = request.form.get("preferred_help_method")
        if preferred == "Meetup":
            mode = "Meetup"
        else:
            mode = "Online"
        preferred_help_method = preferred
        time_needed = request.form.get("time_needed")
        urgency = request.form.get("urgency", "Normal") or "Normal"
        profile = get_logged_in_profile()
        posted_by = profile.name if profile else (request.form.get("posted_by") or "Community Member")
        time_ago = "Just now"
        user_id = session.get("user_id")

        conn = sqlite3.connect(os.path.join(basedir, "project.db"))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO help_requests (title, description, category, preferred_help_method, mode, time_needed, urgency, posted_by, time_ago, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, description, category, preferred_help_method, mode, time_needed, urgency, posted_by, time_ago, user_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("create_help", success=1))

    profile = get_logged_in_profile()
    return render_template("help_create.html", profile=profile)

@app.route('/faq')
def faq():
    page = max(1, request.args.get("page", 1, type=int))
    q = (request.args.get("q") or "").strip()
    cat = (request.args.get("cat") or "All").strip()

    items = list(FAQ_DATA)

    if cat and cat != "All":
        items = [i for i in items if (i.get("category") or "") == cat]

    if q:
        q_lower = q.lower()
        items = [i for i in items if q_lower in (i.get("question") or "").lower() or q_lower in (i.get("answer") or "").lower()]

    items.sort(key=lambda x: x.get("priority", 999))

    total = len(items)
    total_pages = max(1, math.ceil(total / PER_PAGE)) if total else 1
    page = min(page, total_pages)
    start = (page - 1) * PER_PAGE
    faqs = items[start : start + PER_PAGE]

    return render_template("faq.html", faqs=faqs, page=page, total_pages=total_pages, q=q, cat=cat, categories=FAQ_CATEGORIES)

@app.route('/conversations/topic/create', methods=['POST'])
def create_topic():
    global _next_user_topic_id
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    topic_id = _next_user_topic_id
    _next_user_topic_id += 1
    topic_interest[topic_id] = 1
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO topics (id, title, description, category) VALUES (?, ?, ?, ?)",
        (topic_id, title or "New topic", description or "", ""),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("conversations", topic_created=1))

@app.route('/conversations')
def conversations():
    conn = sqlite3.connect(os.path.join(basedir, "project.db"))
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, category FROM topics ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    topics = []
    for row in rows:
        tid = row[0]
        is_seeded = tid in SEEDED_TOPIC_IDS
        if is_seeded:
            icon = TOPICS.get(tid, {}).get("icon") or DEFAULT_CONVERSATION_ICON
            interest_count = SEEDED_INTEREST.get(tid, 10)
        else:
            icon = DEFAULT_CONVERSATION_ICON
            interest_count = topic_interest.get(tid, 1)
        topics.append({
            "id": tid,
            "title": row[1] or "",
            "description": row[2] or "",
            "category": row[3] or "",
            "icon": icon,
            "interest_count": interest_count,
            "is_user_created": not is_seeded,
        })
    return render_template("conversations.html", topics=topics)

@app.route('/conversations/chat', methods=['GET'])
def chat():
    # Support chat from skill exchange (partner_id or author_name)
    raw_partner_id = request.args.get("partner_id")
    author_name = request.args.get("author_name", "").strip()
    help_request_id = request.args.get("help_request")
    source = request.args.get("source", "").strip().lower()
    
    if raw_partner_id and str(raw_partner_id).strip().isdigit():
        if 'user_id' not in session:
            flash('Please log in to chat with this person.', 'warning')
            return redirect(url_for('login', next=request.url))
        partner_user_id = int(raw_partner_id)
        profile = UserProfile.query.filter_by(user_id=partner_user_id).first()
        discussing_offer = request.args.get("discussing") == "1"  # Chat to discuss offer before accepting
        from_offer = request.args.get("from_offer") == "1"  # You're interested in their skill offer
        if source == "skill" and from_offer:
            topic_title = "Skill Exchange – interested in their offer"
            opening_message = "You're interested in their skill offer. Use this chat to arrange when and how you can connect (e.g. time, place, or video call)."
        elif source == "skill":
            topic_title = "Skill Exchange – chat with requester"
            opening_message = "You're offering to help with their skill request. Use this chat to arrange when and how you can connect (e.g. time, place, or video call)."
        elif discussing_offer and help_request_id:
            topic_title = "Help request – discuss this offer"
            opening_message = "You're considering their offer. Use this chat to ask questions, discuss details, or arrange when and how you'd like to connect before accepting."
        else:
            topic_title = "Help request – chat with your helper"
            opening_message = "You accepted their offer to help. Use this chat to arrange when and how you'd like to connect (e.g. time, place, or video call)."
        if profile:
            partner = {
                "name": profile.name or "Chat Partner",
                "bio": (profile.short_intro or "").strip() or "Community member.",
                "avatar": url_for("static", filename="css/ProfilePicture.jpg"),
            }
        else:
            partner = {
                "name": "Chat Partner",
                "bio": "Community member.",
                "avatar": url_for("static", filename="css/ProfilePicture.jpg"),
            }
        suggested_points = [
            "When are you free to connect?",
            "Where would you prefer to meet / online?",
            "Anything I should prepare?",
            "Thank you for connecting!",
        ]
        help_req_id = int(help_request_id) if help_request_id and str(help_request_id).strip().isdigit() else None
        skill_post_id_param = request.args.get("skill_post")
        skill_post_id_val = int(skill_post_id_param) if skill_post_id_param and str(skill_post_id_param).strip().isdigit() else None
        return render_template("chat.html", topic_title=topic_title, partner=partner, opening_message=opening_message, suggested_points=suggested_points,
                               partner_id=partner_user_id, real_chat=True, my_user_id=session.get('user_id'),
                               help_request_id=help_req_id, skill_post_id=skill_post_id_val)
    
    # Skill exchange: no user_id but we have author_name – show chat with display name
    if source == "skill" and author_name:
        from_offer = request.args.get("from_offer") == "1"
        topic_title = "Skill Exchange – interested in their offer" if from_offer else "Skill Exchange – chat with requester"
        partner = {
            "name": author_name,
            "bio": "Offerer from the Skill Exchange." if from_offer else "Requester from the Skill Exchange.",
            "avatar": url_for("static", filename="css/ProfilePicture.jpg"),
        }
        opening_message = "You're interested in their skill offer. Use this chat to arrange when and how you can connect." if from_offer else "You're offering to help with their skill request. Use this chat to arrange when and how you can connect."
        suggested_points = [
            "When are you free to connect?",
            "Where would you prefer to meet / online?",
            "Anything I should prepare?",
            "Thank you for connecting!",
        ]
        return render_template("chat.html", topic_title=topic_title, partner=partner, opening_message=opening_message, suggested_points=suggested_points)

    raw_topic = request.args.get("topic")
    raw_person_id = request.args.get("person_id")
    topic_param = (raw_topic.strip() if raw_topic and isinstance(raw_topic, str) else "") or ""
    person_id_param = (raw_person_id.strip() if raw_person_id and isinstance(raw_person_id, str) else (str(raw_person_id) if raw_person_id is not None else "")) or ""

    resolved = _resolve_topic_param(topic_param)
    if resolved is None:
        topic_id = random.choice(list(TOPICS.keys()))
        topic = TOPICS[topic_id]
    else:
        topic_id, topic = resolved

    if _canonical_topic(topic_param) == "sports & games":
        topic_id, topic = 10, TOPICS[10]

    people = TOPIC_PEOPLE.get(topic_id)
    if not people:
        topic_id = 1
        people = TOPIC_PEOPLE[1]
        topic = TOPICS[1]

    if person_id_param:
        person = None
        for p in people:
            if str(p["id"]) == str(person_id_param):
                person = p
                break
        if person is None:
            person = random.choice(people)
    else:
        person = random.choice(people)

    topic_title = topic.get("title") or "Chat"
    if topic_id in topic_interest:
        topic_interest[topic_id] += 1
    else:
        topic_interest[topic_id] = 1

    partner = {
        "name": person.get("name") or "Chat Partner",
        "bio": person.get("short_bio") or "",
        "avatar": person.get("avatar_url") or "/static/avatar.svg",
    }
    topic_canon = _canonical_topic(topic_title)
    content = (
        CHAT_CONTENT.get(topic_title)
        or next((v for k, v in CHAT_CONTENT.items() if _canonical_topic(k) == topic_canon), None)
        or CHAT_CONTENT_FALLBACK
    )
    opening_message = content.get("opening_message", CHAT_CONTENT_FALLBACK["opening_message"])
    suggested_points = content.get("suggested_points", CHAT_CONTENT_FALLBACK["suggested_points"])
    return render_template("chat.html", topic_title=topic_title, partner=partner, opening_message=opening_message, suggested_points=suggested_points)


# ---------------------------------------------------------
# SOCKET.IO - Real-time chat
# ---------------------------------------------------------
def _conv_room(uid1, uid2, help_request_id=None, skill_post_id=None):
    """Generate consistent room ID - same post = same chat."""
    base = f"conv_{min(uid1, uid2)}_{max(uid1, uid2)}"
    if help_request_id is not None:
        return f"{base}_h{help_request_id}"
    if skill_post_id is not None:
        return f"{base}_s{skill_post_id}"
    return base

@socketio.on('connect')
def handle_connect():
    """On connect, join conversation rooms for the user."""
    user_id = session.get('user_id')
    if user_id:
        emit('user_id', {'user_id': user_id})

@socketio.on('join_chat')
def handle_join_chat(data):
    """Join the room for a specific conversation (scoped by help_request or skill_post)."""
    user_id = session.get('user_id')
    d = data if isinstance(data, dict) else {}
    partner_id = d.get('partner_id')
    help_request_id = d.get('help_request_id')
    skill_post_id = d.get('skill_post_id')
    if user_id and partner_id:
        room = _conv_room(user_id, partner_id, help_request_id, skill_post_id)
        join_room(room)
        emit('joined', {'room': room})

@socketio.on('leave_chat')
def handle_leave_chat(data):
    """Leave a conversation room."""
    d = data if isinstance(data, dict) else {}
    partner_id = d.get('partner_id')
    help_request_id = d.get('help_request_id')
    skill_post_id = d.get('skill_post_id')
    if partner_id:
        user_id = session.get('user_id')
        if user_id:
            room = _conv_room(user_id, partner_id, help_request_id, skill_post_id)
            leave_room(room)

@socketio.on('send_message')
def handle_send_message(data):
    """Receive a message, save to DB, broadcast to room (same post = same chat)."""
    user_id = session.get('user_id')
    if not user_id:
        emit('error', {'msg': 'Not logged in'})
        return
    d = data if isinstance(data, dict) else {}
    partner_id = d.get('partner_id')
    text = (d.get('message') or '').strip()
    help_request_id = d.get('help_request_id')
    skill_post_id = d.get('skill_post_id')
    if not partner_id or not text or len(text) > 5000:
        emit('error', {'msg': 'Invalid message'})
        return
    msg = ChatMessage(sender_id=user_id, receiver_id=partner_id, message=text,
                     help_request_id=help_request_id or None, skill_post_id=skill_post_id or None)
    db.session.add(msg)
    db.session.commit()
    room = _conv_room(user_id, partner_id, help_request_id, skill_post_id)
    # Notify receiver so they know to check the chat (same post)
    sender_profile = UserProfile.query.filter_by(user_id=user_id).first()
    sender_name = sender_profile.name if sender_profile else "Someone"
    preview = text[:60] + ("..." if len(text) > 60 else "")
    with app.test_request_context():
        if help_request_id:
            chat_url = url_for('chat', partner_id=user_id, help_request=help_request_id)
        elif skill_post_id:
            chat_url = url_for('chat', partner_id=user_id, source='skill', skill_post=skill_post_id)
        else:
            chat_url = url_for('chat', partner_id=user_id)
    create_notification(partner_id, 'chat_message', f'{sender_name} sent you a message',
                       preview, chat_url)
    payload = {
        'id': msg.id,
        'sender_id': user_id,
        'receiver_id': partner_id,
        'message': text,
        'created_at': msg.created_at.isoformat() if msg.created_at else None,
        'is_sent': True
    }
    emit('new_message', payload, room=room)

if __name__ == '__main__':
    debug = app.config.get('DEBUG', False)
    socketio.run(app, debug=debug, host='0.0.0.0')