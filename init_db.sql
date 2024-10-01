-- Create the "users" table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);

-- Create the "post" table
CREATE TABLE IF NOT EXISTS post (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    post_time TIMESTAMP NOT NULL DEFAULT NOW(),
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create the "followers" table
CREATE TABLE IF NOT EXISTS followers (
    followed_id INTEGER NOT NULL,
    follower_id INTEGER NOT NULL,
    PRIMARY KEY (followed_id, follower_id),
    FOREIGN KEY (followed_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create the "likes" table
CREATE TABLE IF NOT EXISTS likes (
    like_user INTEGER NOT NULL,
    liked_post INTEGER NOT NULL,
    PRIMARY KEY (like_user, liked_post),
    FOREIGN KEY (like_user) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (liked_post) REFERENCES post(id) ON DELETE CASCADE
);
