from flask import Flask, render_template, request, redirect, url_for, Response, abort, flash
import google.generativeai as genai
import os
import io
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from google.cloud import storage
from PIL import Image  
import tempfile

app = Flask(__name__)
app.secret_key = 'AIzaSyDni6Ch3k-WgsA7m4_XnFvpKrmFVGItZQs'  # Keep this key secure

# Google Cloud credentials and bucket name
BUCKET_NAME = 'kasulabucket223355'
UPLOAD_FOLDER = 'upload'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
background_color = "blue" 

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login page if not logged in

# Dummy users
users_db = {'user1': 'password1', 'user2': 'password2'}

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Google Cloud Storage Upload
def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
    except Exception as e:
        abort(500, description="Error uploading the file. Try again later.")

# Generate image caption using Gemini API
def generate_image_caption(image_path):
    # Setting API key as an environment variable
    os.environ["API_KEY"] = "AIzaSyDni6Ch3k-WgsA7m4_XnFvpKrmFVGItZQs"

    # Configure the generative AI library
    genai.configure(api_key=os.environ["API_KEY"])

    # Open the image using PIL
    image = Image.open(image_path)

    # Call the Gemini model
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = "Generate a caption and description for this image."
    
    # Generate content with the image
    response = model.generate_content([prompt, image])

    return response.text if response else "No caption generated."

# List images in a Google Cloud bucket
def list_blobs(bucket_name, user_folder):
    try:
        storage_client = storage.Client()
        blobs = storage_client.list_blobs(bucket_name, prefix=user_folder)
        return blobs
    except Exception as e:
        abort(500, description="Error fetching images. Try again later.")

# Download blob into memory
def download_blob_into_memory(bucket_name, blob_name):
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        file_obj = io.BytesIO()
        blob.download_to_file(file_obj)
        file_obj.seek(0)
        return file_obj.read()
    except Exception as e:
        abort(404, description="Image not found.")

@app.route('/login', methods=['GET', 'POST'])
def login():
    login_background_color = "lightblue"  # Set the specific color for the login page
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if user exists and password matches
        if username in users_db and users_db[username] == password:
            user = User(username)
            login_user(user)
            return redirect(url_for('upload_file'))
        else:
            flash('Invalid username or password')
    return render_template('login.html', background_color=login_background_color)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def upload_file(): 

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part in the request')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            # Save file locally
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Upload image to user's folder in the cloud
            user_folder = f'{current_user.id}/'
            destination_blob_name = f"{user_folder}{filename}"
            upload_blob(BUCKET_NAME, filepath, destination_blob_name)

            # Generate image caption using Gemini API
            caption = generate_image_caption(filepath)

            # Save caption as .txt file in the same cloud folder
            caption_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{filename}.txt")
            with open(caption_file_path, 'w') as txt_file:
                txt_file.write(caption)
            upload_blob(BUCKET_NAME, caption_file_path, f"{user_folder}{filename}.txt")

            flash('File successfully uploaded and caption generated!')
            return redirect(url_for('gallery'))
    return render_template('upload.html', background_color=background_color)

@app.route('/gallery')
@login_required
def gallery():
    try:
        user_folder = f'{current_user.id}/'
        blobs = list_blobs(BUCKET_NAME, user_folder)
        blob_list = list(blobs)
        image_data = {}
        captions = {}

        for blob in blob_list:
            blob_name = blob.name

            if blob_name.endswith('.txt'):
                # Read the caption file
                caption_bytes = download_blob_into_memory(BUCKET_NAME, blob_name)
                captions[blob_name] = caption_bytes.decode('utf-8').strip()  # Store the caption text
            elif not blob_name.endswith('.txt'):
                # Download the image file
                image_bytes = download_blob_into_memory(BUCKET_NAME, blob_name)
                image_data[blob_name] = image_bytes

        return render_template('gallery.html', image_data=image_data, captions=captions,background_color=background_color)
    except Exception as e:
        abort(500, description=f"Error fetching images: {e}")

@app.route('/images/<filename>')
@login_required
def serve_image(filename):
    try:
        user_folder = f'{current_user.id}/'
        blob_name = f'{user_folder}{filename}'  # Ensure correct blob name format
        image_bytes = download_blob_into_memory(BUCKET_NAME, blob_name)
        return Response(image_bytes, mimetype='image/jpeg')
    except Exception as e:
        abort(404, description=f"Image not found: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
