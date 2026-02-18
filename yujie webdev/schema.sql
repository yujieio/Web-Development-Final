CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    user_type VARCHAR(20) NOT NULL DEFAULT 'Youth',
    date_created DATETIME,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS skill_post (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    skill_type VARCHAR(20) NOT NULL,
    user_type VARCHAR(20) NOT NULL,
    author_name VARCHAR(100),
    profile_picture_url VARCHAR(500),
    user_id INTEGER,
    date_posted DATETIME,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name VARCHAR(100) NOT NULL,
    user_type VARCHAR(20) NOT NULL,
    languages VARCHAR(200),
    short_intro TEXT,
    interaction_type VARCHAR(20) DEFAULT '1-to-1',
    meeting_style VARCHAR(20) DEFAULT 'Online',
    interest_tags VARCHAR(500),
    large_text BOOLEAN DEFAULT 0,
    high_contrast BOOLEAN DEFAULT 0,
    easy_reading BOOLEAN DEFAULT 0,
    total_points INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    date_created DATETIME,
    date_updated DATETIME,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS bingo_prompt (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_text VARCHAR(200) NOT NULL,
    position INTEGER NOT NULL,
    category VARCHAR(50),
    is_active BOOLEAN DEFAULT 1,
    date_created DATETIME
);

CREATE TABLE IF NOT EXISTS bingo_story (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    author_name VARCHAR(100) NOT NULL,
    user_type VARCHAR(20) NOT NULL,
    user_id INTEGER,
    title VARCHAR(200) NOT NULL,
    story_content TEXT NOT NULL,
    photo_url VARCHAR(500),
    points_earned INTEGER DEFAULT 10,
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    is_published BOOLEAN DEFAULT 1,
    date_posted DATETIME,
    date_updated DATETIME,
    FOREIGN KEY (prompt_id) REFERENCES bingo_prompt(id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS bingo_comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL,
    author_name VARCHAR(100) NOT NULL,
    user_id INTEGER,
    comment_text TEXT NOT NULL,
    points_earned INTEGER DEFAULT 2,
    date_posted DATETIME,
    FOREIGN KEY (story_id) REFERENCES bingo_story(id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    date VARCHAR(50) NOT NULL,
    time VARCHAR(50) NOT NULL,
    location VARCHAR(200) NOT NULL,
    capacity INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    organizer_name VARCHAR(100),
    user_id INTEGER,
    date_created DATETIME,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS journal_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    mood VARCHAR(50),
    tags VARCHAR(500),
    date_posted DATETIME,
    author VARCHAR(100) NOT NULL,
    likes INTEGER DEFAULT 0,
    liked_by VARCHAR(500) DEFAULT ''
);

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
    status TEXT DEFAULT 'Open',
    user_id INTEGER,
    accepted_offer_id INTEGER
);

CREATE TABLE IF NOT EXISTS help_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    help_request_id INTEGER,
    offer_text TEXT,
    availability TEXT,
    help_mode TEXT,
    user_id INTEGER
);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY,
    title TEXT,
    description TEXT,
    category TEXT
);

CREATE TABLE IF NOT EXISTS chat_message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    help_request_id INTEGER,
    skill_post_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES user(id),
    FOREIGN KEY (receiver_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS notification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ntype VARCHAR(50) NOT NULL,
    title VARCHAR(200),
    message TEXT,
    link_url VARCHAR(500),
    is_read INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE INDEX IF NOT EXISTS idx_user_username ON user(username);
CREATE INDEX IF NOT EXISTS idx_user_email ON user(email);
CREATE INDEX IF NOT EXISTS idx_user_profile_user_id ON user_profile(user_id);
CREATE INDEX IF NOT EXISTS idx_skill_post_category ON skill_post(category);
CREATE INDEX IF NOT EXISTS idx_skill_post_skill_type ON skill_post(skill_type);
CREATE INDEX IF NOT EXISTS idx_bingo_story_prompt_id ON bingo_story(prompt_id);
CREATE INDEX IF NOT EXISTS idx_bingo_comment_story_id ON bingo_comment(story_id);
CREATE INDEX IF NOT EXISTS idx_help_offers_request_id ON help_offers(help_request_id);
CREATE INDEX IF NOT EXISTS idx_journal_entry_author ON journal_entry(author);
CREATE INDEX IF NOT EXISTS idx_event_date ON event(date);
