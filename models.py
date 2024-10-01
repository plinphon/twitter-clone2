from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)  

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Post(db.Model):
    __tablename__ = 'post'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    text = db.Column(db.String, nullable=False)
    post_time = db.Column(db.DateTime, nullable=False, default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('posts', lazy=True))
    # Use 'post_likes' as the backref name to avoid overlap
    likes = db.relationship("Like", back_populates="post", cascade="all, delete-orphan")

class Follower(db.Model):
    __tablename__ = 'followers'

    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True, nullable=False)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True, nullable=False)

    follower = db.relationship('User', foreign_keys=[follower_id])
    followed = db.relationship('User', foreign_keys=[followed_id])

class Like(db.Model):
    __tablename__ = 'likes'

    like_user = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True, nullable=False)
    liked_post = db.Column(db.Integer, db.ForeignKey('post.id'), primary_key=True, nullable=False)

    user = db.relationship('User', foreign_keys=[like_user])
    post = db.relationship('Post', back_populates='likes')  # Use back_populates to avoid overlap
