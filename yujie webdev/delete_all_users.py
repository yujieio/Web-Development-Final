"""Delete all user accounts and their posts. Run: python delete_all_users.py"""
import os
import sqlite3

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from app import (
    BingoStoryLike, BingoComment, BingoStory, UserPurchase,
    Notification, ChatMessage, UserProfile, SkillPost,
    JournalEntry, Event, MemoryItem, User,
)

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, "project.db")

def delete_all():
    with app.app_context():
        # SQLAlchemy models - delete in order (children before parents)
        BingoStoryLike.query.delete()
        BingoComment.query.delete()
        BingoStory.query.delete()
        UserPurchase.query.delete()
        Notification.query.delete()
        ChatMessage.query.delete()
        UserProfile.query.delete()
        SkillPost.query.delete()
        JournalEntry.query.delete()
        Event.query.delete()
        MemoryItem.query.delete()
        User.query.delete()
        db.session.commit()

        # Raw SQLite tables (help system)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM help_offers")
            cursor.execute("DELETE FROM help_requests")
            conn.commit()
        except Exception:
            pass
        conn.close()

        print("All users and posts have been deleted.")

if __name__ == "__main__":
    delete_all()
