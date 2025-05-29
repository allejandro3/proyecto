from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, Response
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import datetime 

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-larga-y-aleatoria-por-defecto') # Ejemplo con fallback

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/pop' # Conectado a la BD "pop" en XAMPP
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Desactiva notificaciones innecesarias

# Define el directorio desde donde se servirán los archivos descargables.
# Es buena práctica usar una ruta absoluta o relativa a la aplicación y definirlo temprano.
DOWNLOAD_DIRECTORY = os.path.join(app.root_path, 'archivos_descargables')

# Inicializa la extensión SQLAlchemy
db = SQLAlchemy(app)

# --- Configuración de Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Página a la que redirigir si se intenta acceder a una ruta protegida sin estar logueado
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "info" # Categoría de mensaje flash para Bootstrap (si usas Bootstrap para alertas)

@login_manager.user_loader
def load_user(user_id):
    # Flask-Login usa esto para recargar el objeto usuario desde el ID de usuario almacenado en la sesión
    return User.query.get(int(user_id))

# --- Modelo de Base de Datos ---
class User(UserMixin, db.Model): # UserMixin añade las propiedades requeridas por Flask-Login (is_authenticated, etc.)
    id = db.Column(db.Integer, primary_key=True) # Clave primaria autoincremental
    email = db.Column(db.String(120), unique=True, nullable=False) # Email único, no puede ser nulo
    password_hash = db.Column(db.String(255), nullable=False) # Hash de la contraseña, aumentado para evitar truncamiento

    # UserMixin requiere el método get_id(), que db.Model ya proporciona a través de la columna 'id'.
    # No necesitas definirlo explícitamente si tu clave primaria se llama 'id'.

    def __repr__(self):
        return f'<User {self.email}>'

# Define una ruta para la página principal ('/')
@app.route('/')
def index() -> str:
    # Ejemplo: Puedes pasar datos a tu plantilla index si es necesario
    titulo_web = "Página Principal"
    # current_user estará disponible en todas las plantillas gracias a Flask-Login
    # y a que LoginManager está inicializado con la app.
    return render_template('index.html', titulo=titulo_web)

# Ruta para la página de inicio de sesión
@app.route('/login', methods=['GET', 'POST'])
def login() -> str:
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Validación básica para campos no vacíos
        if not email or not password:
            flash('Por favor, ingresa tanto el correo electrónico como la contraseña.', 'error')
            return redirect(url_for('login'))

        # Buscar usuario en la base de datos por email
        user = User.query.filter_by(email=email).first() # .first() obtiene el primer resultado o None

        # Verificar si el usuario existe y la contraseña coincide con el hash guardado
        if user and check_password_hash(user.password_hash, password):
            login_user(user) # Inicia la sesión para el usuario con Flask-Login
            flash('¡Inicio de sesión exitoso!', 'success')
            # Redirigir a la página principal (index)
            return redirect(url_for('dashboard'))
        else:
            # Credenciales incorrectas
            flash('Correo electrónico o contraseña incorrectos.', 'error')
            # print("LOGIN: Usuario no encontrado o check_password_hash retornó False") # DEBUG - Comentado o eliminado
            # Volver a mostrar el formulario de login
            return redirect(url_for('login'))
    # Si es GET, solo muestra el formulario de login
    # Asegúrate de tener 'templates/login.html'
    return render_template('login.html')

# Ruta para la página de registro
@app.route('/register', methods=['GET', 'POST'])
def register() -> str:
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Validación básica
        if not email or not password:
            flash('Por favor, completa todos los campos.', 'error')
            return redirect(url_for('register')) # Vuelve a mostrar el formulario

        # Verificar si el email ya existe en la BD
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Este correo electrónico ya está registrado. Intenta iniciar sesión.', 'error')
            return redirect(url_for('register'))

        # Hashear la contraseña antes de guardarla
        hashed_password = generate_password_hash(password)
        # print(f"REGISTER: Hash generado: {hashed_password}") # DEBUG - Comentado o eliminado

        # Crear una nueva instancia del modelo User y guardar en BD
        new_user = User(email=email, password_hash=hashed_password)
        try:
            db.session.add(new_user) # Añadir el nuevo usuario a la sesión de la BD
            db.session.commit() # Guardar los cambios en la BD
            flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback() # Revertir cambios si hay un error
            flash(f'Ocurrió un error durante el registro: {str(e)}', 'error')
            # Podrías loggear el error 'e' para depuración
            return redirect(url_for('register'))

    # Si es GET, solo muestra el formulario de registro
    # Asegúrate de tener 'templates/register.html'
    return render_template('register.html')

# Ruta para cerrar sesión
@app.route('/logout')
@login_required # Solo usuarios logueados pueden cerrar sesión
def logout() -> Response:
    logout_user() # Cierra la sesión del usuario actual
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('index')) # Redirige a la página de Inicio

# Nueva ruta para la página principal después del login
@app.route('/dashboard')
@login_required # Protege esta ruta, solo usuarios logueados pueden acceder
def dashboard() -> str:
    current_year = datetime.datetime.now().year
    # current_user (de Flask-Login) contiene el objeto del usuario actualmente logueado
    # y está disponible automáticamente en las plantillas.
    return render_template('dashboard.html', current_year=current_year)

# --- Ruta para mostrar archivos de una categoría específica ---
@app.route('/downloads/<category>')
@login_required
def show_download_category(category: str) -> str:
    """Muestra las aplicaciones (subdirectorios) disponibles en una categoría."""
    category_path = os.path.join(DOWNLOAD_DIRECTORY, category)
    if not os.path.isdir(category_path):
        flash(f"La categoría '{category}' no fue encontrada.", "error")
        return redirect(url_for('dashboard'))

    try:
        # Listar solo subdirectorios (nombres de las apps)
        apps = [d for d in os.listdir(category_path) if os.path.isdir(os.path.join(category_path, d))]
        apps.sort() # Ordena la lista de apps alfabéticamente
    except OSError:
        flash(f"No se pudo acceder a las aplicaciones de la categoría '{category}'.", "error")
        apps = [] # Lista vacía si hay un error al listar

    # Renderiza una plantilla que lista los nombres de las apps
    return render_template('app_category_list.html', category=category, apps=apps, current_year=datetime.datetime.now().year)

# --- Ruta para mostrar versiones de una app específica ---
@app.route('/downloads/<category>/<app_name>')
@login_required
def show_app_versions(category: str, app_name: str) -> str:
    """Muestra los archivos (versiones) disponibles para una aplicación específica."""
    app_path = os.path.join(DOWNLOAD_DIRECTORY, category, app_name)
    if not os.path.isdir(app_path):
        flash(f"La aplicación '{app_name}' en la categoría '{category}' no fue encontrada.", "error")
        return redirect(url_for('show_download_category', category=category))

    try:
        # Listar solo archivos (versiones de la app)
        versions = [f for f in os.listdir(app_path) if os.path.isfile(os.path.join(app_path, f))]
        versions.sort() # Ordena la lista de versiones alfabéticamente
    except OSError:
        flash(f"No se pudo acceder a las versiones de la aplicación '{app_name}'.", "error")
        versions = []
    return render_template('app_version_list.html', category=category, app_name=app_name, versions=versions, current_year=datetime.datetime.now().year)

@app.route('/download/<path:filename>')
@login_required # Asegura que solo usuarios logueados puedan descargar
def download_file(filename: str) -> Response:
    try:
        # send_from_directory maneja la seguridad para evitar accesos fuera del directorio especificado.
        # as_attachment=True fuerza la descarga del archivo en lugar de intentar mostrarlo en el navegador.
        return send_from_directory(DOWNLOAD_DIRECTORY, filename, as_attachment=True)
    except FileNotFoundError:
        flash("El archivo solicitado no fue encontrado.", "error")
        return redirect(url_for('dashboard'))

# Bloque para ejecutar la app en desarrollo (si no lo tenías ya)
if __name__ == '__main__':
    # ¡Importante! Crear las tablas si no existen antes de correr la app por primera vez
    with app.app_context():
        db.create_all()
    # Ejecutar la aplicación en modo debug (¡solo para desarrollo!)
    app.run(debug=True)
