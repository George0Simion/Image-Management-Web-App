from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from PIL import Image, ImageFilter, ImageOps
import random

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'your_secret_key'
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

users = [User(id=1, username='admin', password='secret')]

@login_manager.user_loader
def load_user(user_id):
    for user in users:
        if str(user.id) == str(user_id):
            return user
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        for user in users:
            if user.username == username and user.password == password:
                login_user(user)
                return redirect(url_for('index'))
        return 'Invalid username or password'

    thumbnails = []
    for folder in next(os.walk(app.config['UPLOAD_FOLDER']))[1]:
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder)
        for filename in os.listdir(folder_path):
            if filename.endswith("_thumb"):
                thumbnails.append(url_for('uploaded_file', foldername=folder, filename=filename))
    
    return render_template('login.html', thumbnails=thumbnails)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    folder_path = UPLOAD_FOLDER
    folders = []

    for foldername in next(os.walk(folder_path))[1]:
        folder_full_path = full_path(foldername)
        images = [f for f in os.listdir(folder_full_path) if allowed_file(f)]
        folder = {
            'name': foldername,
            'image': random.choice(images) if images else None
        }
        folders.append(folder)

    return render_template('index.html', folders=folders)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def full_path(directory):
    return os.path.join(UPLOAD_FOLDER, directory)

@app.route('/folder/<foldername>')
@login_required
def folder(foldername):
    folder_path = full_path(foldername)
    files = [f for f in os.listdir(folder_path) if allowed_file(f)]
    return render_template('folder.html', foldername=foldername, files=files)

@app.route('/upload/<foldername>', methods=['POST'])
@login_required
def upload_file(foldername):
    file = request.files['file']
    photo_name = request.form.get('photoName', '').strip()
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        if photo_name:
            base, ext = os.path.splitext(filename)
            filename = f"{photo_name}{ext}"
        file.save(os.path.join(full_path(foldername), filename))
        create_thumbnail(os.path.join(full_path(foldername), filename))
    return redirect(url_for('folder', foldername=foldername))

@app.route('/create-folder', methods=['POST'])
def create_folder():
    folder_name = request.form['folder_name']
    os.makedirs(full_path(folder_name), exist_ok=True)
    return redirect(url_for('index'))

@app.route('/uploads/<foldername>/<filename>')
def uploaded_file(foldername, filename):
    return send_from_directory(full_path(foldername), filename)

def create_thumbnail(image_path):
    size = (100, 100)
    image = Image.open(image_path)
    image.thumbnail(size)
    base, ext = os.path.splitext(image_path)
    thumbnail_path = f"{base}_thumb"
    image.save(thumbnail_path, "JPEG")
    return thumbnail_path

@app.route('/apply_filter/<foldername>/<filename>', methods=['POST'])
@login_required
def apply_filter(foldername, filename):
    filter_type = request.form['filter']
    full_image_path = os.path.join(app.config['UPLOAD_FOLDER'], foldername, filename)
    if '_thumb' in full_image_path:
        return redirect(url_for('folder', foldername=foldername))  # Avoid applying filters to thumbnails
    backups_folder = os.path.join(app.config['UPLOAD_FOLDER'], foldername, 'backups')
    if not os.path.exists(backups_folder):
        os.makedirs(backups_folder)
    backup_image_path = os.path.join(backups_folder, f"backup_{filename}")

    try:
        if filter_type == 'revert':
            if os.path.exists(backup_image_path):
                os.replace(backup_image_path, full_image_path)
                create_thumbnail(full_image_path)
            return redirect(url_for('folder', foldername=foldername))

        if not os.path.exists(backup_image_path):
            os.rename(full_image_path, backup_image_path)
        else:
            os.remove(backup_image_path)
            os.rename(full_image_path, backup_image_path)

        image = Image.open(backup_image_path)

        if filter_type == 'grayscale':
            image = ImageOps.grayscale(image)
        elif filter_type == 'blur':
            image = image.filter(ImageFilter.BLUR)
        elif filter_type == 'rotate':
            image = image.rotate(90, expand=True)

        image.save(full_image_path)
        create_thumbnail(full_image_path)

    except Exception as e:
        print(f"Error applying filter: {e}")

    return redirect(url_for('folder', foldername=foldername))

@app.route('/delete/<foldername>/<filename>', methods=['POST'])
@login_required
def delete_image(foldername, filename):
    full_image_path = os.path.join(app.config['UPLOAD_FOLDER'], foldername, filename)
    base, ext = os.path.splitext(filename)
    thumbnail_filename = f"{base}_thumb"
    thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], foldername, thumbnail_filename)
    backups_folder = os.path.join(app.config['UPLOAD_FOLDER'], foldername, 'backups')
    backup_image_path = os.path.join(backups_folder, f"backup_{filename}")

    try:
        if os.path.exists(full_image_path):
            os.remove(full_image_path)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        if os.path.exists(backup_image_path):
            os.remove(backup_image_path)
    except Exception as e:
        print(f"Error deleting image: {e}")

    return redirect(url_for('folder', foldername=foldername))

@app.route('/resize_image/<foldername>/<filename>', methods=['POST'])
@login_required
def resize_image(foldername, filename):
    width = int(request.form['width'])
    height = int(request.form['height'])
    full_image_path = os.path.join(app.config['UPLOAD_FOLDER'], foldername, filename)
    if '_thumb' in full_image_path:
        return redirect(url_for('folder', foldername=foldername))
    backups_folder = os.path.join(app.config['UPLOAD_FOLDER'], foldername, 'backups')
    if not os.path.exists(backups_folder):
        os.makedirs(backups_folder)
    backup_image_path = os.path.join(backups_folder, f"backup_{filename}")

    try:
        if not os.path.exists(backup_image_path):
            os.rename(full_image_path, backup_image_path)
        else:
            os.remove(backup_image_path)
            os.rename(full_image_path, backup_image_path)

        image = Image.open(backup_image_path)
        resized_image = image.resize((width, height))
        resized_image.save(full_image_path)

        create_thumbnail(full_image_path)

    except Exception as e:
        print(f"Error resizing image: {e}")

    return redirect(url_for('folder', foldername=foldername))

@app.route('/delete_folder/<foldername>', methods=['GET'])
@login_required
def delete_folder(foldername):
    folder_path = full_path(foldername)

    try:
        if os.path.exists(folder_path):
            for root, dirs, files in os.walk(folder_path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(folder_path)
        else:
            print(f"Folder {folder_path} does not exist.")
    except Exception as e:
        print(f"Error deleting folder: {e}")

    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == "__main__":
    app.run(host="0.0.0.0")
