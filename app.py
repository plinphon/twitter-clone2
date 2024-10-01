from gevent import monkey
monkey.patch_all()

from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

from werkzeug.security import check_password_hash  # Import check_password_hash

from flask import Flask, render_template, redirect, url_for, flash, session, request, jsonify
from forms import SignupForm, LoginForm
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from models import db, User, Post, Follower, Like

from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)

# Flask configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:mysecretpassword@localhost:5432/tvitter'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'mysecretkey'

db.init_app(app)

# Initialize Redis and SocketIO for WebSocket communication
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*")


# Ensure database tables are created
with app.app_context():
    db.create_all()

# Routes
@app.route('/', methods=['GET', 'POST'])
def index():
    current_user_id = session.get('user_id')
    if not current_user_id:
        flash("You need to log in first.")
        return redirect(url_for('login'))
    
    current_username = db.session.query(User.username).filter_by(id=current_user_id).first()
    current_username = current_username[0] if current_username else None



    return render_template('index.html',current_username= current_username )

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    
    if form.validate_on_submit():
        # Check if the username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        
        if existing_user:
            flash('Username already taken. Please choose a different one.', 'error')
            return redirect(url_for('signup'))
        
        # If the username is not taken, create a new user
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('User created successfully!')
        return redirect(url_for('login'))
    
    return render_template('signup.html', form=form)

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()  # Assuming you are using a form class
    if form.validate_on_submit():
        # Logic for user authentication
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.')

    # Pass `user` as None if not logged in
    return render_template('login.html', form=form, user=None)


# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.')
    return redirect(url_for('index'))

# Handle new post event
@socketio.on('new_post')
def handle_new_post(data):
    emit('post_update', data, broadcast=True)

# Create new post route
@app.route('/post', methods=['POST'])
def post():
    if 'user_id' not in session:
        flash('You need to be logged in to post.')
        return redirect(url_for('login'))
    
    # Get form data
    content = request.form.get('content')
    if not content:
        flash('Post content cannot be empty.')
        return redirect(url_for('index'))
    
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found.')
        return redirect(url_for('login'))

    # Create a new post
    new_post = Post(text=content, user_id=user.id, post_time=datetime.utcnow())
    db.session.add(new_post)
    db.session.commit()

    # Emit the post update event
    new_post_time = new_post.post_time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"Emitting post update: {content} by {user.username}")
    socketio.emit('post_update', {
    'username': user.username,
    'content': content,
    'post_time': new_post_time
    })  # Proper broadcast without specifying "to"


    flash('Your post has been created!')
    return redirect(url_for('index'))

@app.route('/api/posts', methods=['GET'])
def get_posts():
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify([])  # Return an empty list if the user is not logged in

    followed_ids = db.session.query(Follower.followed_id).filter_by(follower_id=current_user_id).all()
    followed_ids = [f[0] for f in followed_ids]
    followed_ids.append(current_user_id)  # Include own posts

    liked_posts = db.session.query(Like.liked_post).filter_by(like_user=current_user_id).all()
    likes = {like[0] for like in liked_posts}  # Use set for faster lookup

    posts = (
        db.session.query(Post, func.count(Like.liked_post).label('like_count'), User.username)
        .outerjoin(Like, Post.id == Like.liked_post)
        .join(User, Post.user_id == User.id)
        .filter(Post.user_id.in_(followed_ids))
        .group_by(Post.id, Post.text, Post.post_time, Post.user_id, User.username)
        .order_by(Post.post_time.desc())
        .all()
    )

    # Prepare posts data for JSON response
    posts_data = [{
        'id': post.id,
        'text': post.text,
        'username': username,
        'post_time': post.post_time.strftime('%Y-%m-%d %H:%M'),
        'likes': like_count,
        'user_has_liked': post.id in likes,  # Check if the current user has liked this post
        'is_owner': post.user_id == current_user_id
    } for post, like_count, username in posts]

    return jsonify(posts_data)

@app.route('/api/posts/<username>', methods=['GET'])
def get_user_posts(username):
    user = User.query.filter_by(username=username).first_or_404()

    # Get the current user ID for like checking
    current_user_id = session.get('user_id')

    # Fetch posts for the specific user
    posts = (
        db.session.query(Post)
        .filter_by(user_id=user.id)
        .order_by(Post.post_time.desc())  # Order by post time descending
        .all()
    )

    # Fetch user likes for the current user
    liked_posts = {like.liked_post for like in Like.query.filter_by(like_user=current_user_id).all()} if current_user_id else set()

    # Prepare posts data
    posts_data = []
    for post in posts:
        posts_data.append({
            'id': post.id,
            'text': post.text,
            'username': user.username,
            'post_time': post.post_time.strftime('%Y-%m-%d %H:%M'),  # Ensure post_time is a string
            'likes': len(post.likes),  # Use the count of likes, not the Like object
            'user_has_liked': post.id in liked_posts,  # Check if the current user has liked this post
            'is_owner': post.user_id == current_user_id  # Check if the current user is the owner of the post
        })

    return jsonify(posts_data)  # Return the JSON response









@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': "You need to be logged in to delete posts."}), 403

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found.'}), 404

    if post.user_id != user_id:
        return jsonify({'error': 'You cannot delete this post.'}), 403

    db.session.delete(post)
    db.session.commit()

    socketio.emit('post_deleted', {'post_id': post_id}, namespace='/')

    return jsonify({'message': 'Post deleted successfully.'})


@app.route('/test_emit', methods=['GET'])
def test_emit():
    print("Manually emitting test event")
    # Emit a basic test event to see if clients are receiving events
    socketio.emit('test_event', {
        'message': 'This is a test event from the server',
        'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })
    return "Test event emitted"


# Search user route
# Search user route
@app.route('/search', methods=['GET'])
def search():
    current_username = session.get('username')
    query = request.args.get('q')

    if not query:
        flash('Search cannot be empty.')
        return redirect(url_for('index'))

    # Use case-insensitive search
    user = User.query.filter(User.username.ilike(query)).first()

    if user and user.username == current_username:
        return redirect(url_for('profile', username=current_username))
    
    if user:
        return redirect(url_for('profile', username=user.username))
    else:
        flash('No user found.')
        return redirect(url_for('index'))

@app.route('/profile/<username>', methods=['GET'])
def profile(username):
    current_user_id = session.get('user_id')
    current_username = db.session.query(User.username).filter_by(id=current_user_id).first()
    current_username = current_username[0] if current_username else None

    user = User.query.filter_by(username=username).first_or_404()

    # Fetch posts for this user
    posts = (
        db.session.query(Post)
        .filter_by(user_id=user.id)
        .order_by(Post.post_time.desc())
        .all()
    )

    # Check if the current user follows this user
    followed = Follower.query.filter_by(follower_id=current_user_id, followed_id=user.id).first() is not None

    return render_template('profile.html', user=user, posts=posts, followed=followed, current_username=current_username)


# Follow user route
@app.route('/follow/<username>', methods=['POST'])
def follow(username):
    current_user_id = session.get('user_id')
    user_to_follow = User.query.filter_by(username=username).first()

    if not user_to_follow:
        flash('User not found.')
        return redirect(url_for('index'))
    
    if user_to_follow.id == current_user_id:
        flash('You cannot follow yourself.')
        return redirect(url_for('profile', username=username))

    new_follower = Follower(followed_id=user_to_follow.id, follower_id=current_user_id)
    db.session.add(new_follower)
    db.session.commit()
    flash(f'You are now following {username}.')

    return redirect(url_for('profile', username=username))

# Unfollow user route
@app.route('/unfollow/<username>', methods=['POST'])
def unfollow(username):
    if 'user_id' not in session:
        flash('You need to be logged in to unfollow users.')
        return redirect(url_for('login'))

    user_to_unfollow = User.query.filter_by(username=username).first()
    if not user_to_unfollow:
        flash('User not found.')
        return redirect(url_for('index'))

    existing_follow = Follower.query.filter_by(followed_id=user_to_unfollow.id, follower_id=session['user_id']).first()

    if existing_follow:
        db.session.delete(existing_follow)
        db.session.commit()
        flash(f'You have unfollowed {username}.')
    else:
        flash(f'You were not following {username}.')

    return redirect(url_for('profile', username=username))

@app.route('/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': "You need to be logged in to like posts."}), 403

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found.'}), 404

    existing_like = Like.query.filter_by(like_user=user_id, liked_post=post_id).first()
    if existing_like:
        return jsonify({'message': 'You already liked this post.'}), 400

    # Add new like
    new_like = Like(like_user=user_id, liked_post=post_id)
    db.session.add(new_like)
    db.session.commit()

    like_count = Like.query.filter_by(liked_post=post_id).count()
    socketio.emit('like_update', {
        'post_id': post_id,
        'like_count': like_count,
        'user_has_liked': True
    })
    return jsonify({'likes': like_count, 'user_has_liked': True})


@app.route('/unlike_post/<int:post_id>', methods=['POST'])
def unlike_post(post_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': "You need to be logged in to unlike posts."}), 403

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found.'}), 404

    existing_like = Like.query.filter_by(like_user=user_id, liked_post=post_id).first()
    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        
        like_count = Like.query.filter_by(liked_post=post_id).count()
        socketio.emit('like_update', {
            'post_id': post_id,
            'like_count': like_count,
            'user_has_liked': False
        })
        return jsonify({'likes': like_count, 'user_has_liked': False})
    
    # Return an error message if the user hasn't liked the post yet
    return jsonify({'message': "You haven't liked this post yet."}), 400





# Run the server using SocketIO with gevent
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001)
