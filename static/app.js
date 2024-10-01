// Socket.IO connection
var socket = io.connect('http://' + document.domain + ':' + location.port);

// Confirm socket connection
socket.on('connect', function() {
    console.log("Socket connected");
});

socket.on('disconnect', function() {
    console.log("Socket disconnected");
});

function fetchPosts() {
    fetch('/api/posts')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            const postsList = document.querySelector('.posts-list');
            postsList.innerHTML = ''; // Clear existing posts

            data.forEach(post => {
                const postItem = document.createElement('li');
                postItem.className = 'post-item';
                postItem.id = `post-${post.id}`;
                postItem.innerHTML = `
                    <div class="post-header">
                        <span class="post-username">${post.username}</span>
                        <span class="post-time">${post.post_time}</span>
                    </div>
                    <div class="post-content">${post.text}</div>
                    <div class="like-count">${post.likes} likes</div>
                    <form class="like-form" action="/${post.user_has_liked ? 'unlike' : 'like'}/${post.id}" method="POST" style="display:inline;">
                        <button type="submit" class="btn like-btn" data-post-id="${post.id}">
                            ${post.user_has_liked ? 'Unlike' : 'Like'}
                        </button>
                    </form>
                    ${post.is_owner ? `
                    <form class="delete-form" action="/delete_post/${post.id}" method="POST" style="display:inline;">
                        <button type="submit" class="btn delete-btn" data-post-id="${post.id}">Delete</button>
                    </form>
                    ` : ''}
                `;
                postsList.appendChild(postItem);
            });
        })
        .catch(error => {
            console.error('Error fetching posts:', error); // Log the fetch error
        });
        
}


function fetchUserPosts(username) {
    fetch(`/api/posts/${username}`)  // Fetch posts for the specific user
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            const postsList = document.querySelector('.posts-list');
            postsList.innerHTML = ''; // Clear existing posts

            data.forEach(post => {
                const postItem = document.createElement('li');
                postItem.className = 'post-item';
                postItem.id = `post-${post.id}`;
                postItem.innerHTML = `
                    <div class="post-header">
                        <span class="post-username">${post.username}</span>
                        <span class="post-time">${post.post_time}</span>
                    </div>
                    <div class="post-content">${post.text}</div>
                    <div class="like-count">${post.likes} likes</div>
                    <form class="like-form" action="/${post.user_has_liked ? 'unlike' : 'like'}/${post.id}" method="POST" style="display:inline;">
                        <button type="submit" class="btn like-btn" data-post-id="${post.id}">
                            ${post.user_has_liked ? 'Unlike' : 'Like'}
                        </button>
                    </form>
                    ${post.is_owner ? `<form class="delete-form" action="/delete_post/${post.id}" method="POST" style="display:inline;">
                        <button type="submit" class="btn delete-btn" data-post-id="${post.id}">Delete</button>
                    </form>` : ''}
                `;
                postsList.appendChild(postItem);
            });
        })
        .catch(error => {
            console.error('Error fetching user posts:', error); // Log the fetch error
        });
}

// Call fetchUserPosts with the username when the profile page loads
document.addEventListener('DOMContentLoaded', function() {
    const username = "{{ user.username }}"; // Get the username from the server-side
    fetchUserPosts(username); // Fetch posts for this user
});


// Call fetchPosts on DOMContentLoaded
document.addEventListener('DOMContentLoaded', fetchPosts);


// Call fetchPosts with the username when the profile page loads
document.addEventListener('DOMContentLoaded', function() {
    const username = "{{ user.username }}"; // Get the username from the server-side
    fetchPosts(username); // Fetch posts for this user
});

// Listen for post updates from Socket.IO
socket.on('post_update', function(data) {
    console.log("New post received:", data);
    fetchPosts(data.username); // Re-fetch posts for the updated user
});

document.addEventListener('click', function(event) {
    if (event.target.classList.contains('like-btn')) {
        event.preventDefault(); // Prevent default form submission
        const form = event.target.closest('form');
        const postId = form.querySelector('.like-btn').dataset.postId;

        // Determine the action URL based on the button text
        const action = event.target.textContent.trim() === 'Like' ? `/like_post/${postId}` : `/unlike_post/${postId}`;

        console.log('Action URL:', action); // Debug log for action URL

        fetch(action, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errData => {
                    console.error('Error response:', errData); // Log the error response
                    throw new Error(errData.message || 'Something went wrong');
                });
            }
            return response.json(); // Parse the successful response as JSON
        })
        .then(data => {
            // Update the UI with the response data
            const postItem = document.getElementById(`post-${postId}`);
            const likeCountElement = postItem.querySelector('.like-count');
            likeCountElement.textContent = `${data.likes} likes`; // Update like count
            event.target.textContent = data.user_has_liked ? 'Unlike' : 'Like'; // Update button text

            // Emit a socket event for real-time updates
            socket.emit('like_update', {
                post_id: postId,
                like_count: data.likes,
                user_has_liked: data.user_has_liked
            });
        })
        .catch(error => {
            console.error('Error during like/unlike operation:', error.message); // Log the error message
            alert(`Error: ${error.message}`); // Notify the user of the error
        });
    }
});

socket.on('like_update', function(data) {
    const postItem = document.getElementById(`post-${data.post_id}`);
    if (postItem) {
        const likeCountElement = postItem.querySelector('.like-count');
        likeCountElement.textContent = `${data.like_count} likes`; // Update like count
        const likeButton = postItem.querySelector('.like-btn');
        likeButton.textContent = data.user_has_liked ? 'Unlike' : 'Like'; // Update button text
    }
});

socket.on('post_deleted', function(data) {
    const postItem = document.getElementById(`post-${data.post_id}`);
    if (postItem) {
        postItem.remove(); // Remove the post from the DOM
    }
});

document.addEventListener('click', function(event) {
    if (event.target.classList.contains('delete-btn')) {
        event.preventDefault(); // Prevent default form submission
        const form = event.target.closest('form');
        const postId = form.querySelector('.delete-btn').dataset.postId;

        // Confirm deletion
        if (confirm('Are you sure you want to delete this post?')) {
            const action = `/delete_post/${postId}`; // Correct action URL
            console.log('Action URL:', action); // Log the action URL

            fetch(action, {
                method: 'POST'
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errData => {
                        console.error('Error response:', errData); // Log the error response
                        throw new Error(errData.message || 'Something went wrong');
                    });
                }
                return response.json(); // Parse the successful response as JSON
            })
            .then(data => {
                console.log(data.message); // Log success message
                socket.emit('post_deleted', { post_id: postId }); // Emit deletion event for real-time update
            })
            .catch(error => {
                console.error('Error during delete operation:', error.message); // Log the error message
                alert(`Error: ${error.message}`); // Notify the user of the error
            });
        }
    }
});

// Fetch posts on page load
document.addEventListener('DOMContentLoaded', function() {
    const username = "{{ user.username }}"; // Get the username from the server-side
    fetchPosts(username); // Fetch posts for this user
});
