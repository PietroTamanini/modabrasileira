from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import json
import os
from datetime import datetime
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Criar pastas necessárias
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

# Arquivos JSON
USERS_FILE = 'data/users.json'
PRODUCTS_FILE = 'data/products.json'

# Inicializar arquivos JSON se não existirem
def init_json_files():
    if not os.path.exists(USERS_FILE):
        # Admin padrão: admin@modabrasileira.com / admin123
        admin = {
            'email': 'admin@modabrasileira.com',
            'password': generate_password_hash('admin123'),
            'is_admin': True
        }
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'users': [admin]}, f, indent=2, ensure_ascii=False)
    
    if not os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'products': []}, f, indent=2, ensure_ascii=False)

init_json_files()

# Funções auxiliares para JSON
def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Decorador para rotas que precisam de login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para rotas admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session or not session.get('is_admin'):
            flash('Acesso negado. Apenas administradores.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Rotas
@app.route('/')
def index():
    try:
        data = load_json(PRODUCTS_FILE)
        products = data.get('products', [])
    except (FileNotFoundError, json.JSONDecodeError):
        init_json_files()
        products = []
    return render_template('index.html', products=products)

@app.route('/produto/<int:product_id>')
def product_detail(product_id):
    try:
        data = load_json(PRODUCTS_FILE)
        products = data.get('products', [])
        product = next((p for p in products if p['id'] == product_id), None)
        if not product:
            flash('Produto não encontrado', 'error')
            return redirect(url_for('index'))
        return render_template('product_detail.html', product=product)
    except (FileNotFoundError, json.JSONDecodeError):
        flash('Erro ao carregar produtos', 'error')
        return redirect(url_for('index'))

@app.route('/cadastro', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Preencha todos os campos', 'error')
            return redirect(url_for('register'))
        
        data = load_json(USERS_FILE)
        users = data.get('users', [])
        
        if any(u['email'] == email for u in users):
            flash('Email já cadastrado', 'error')
            return redirect(url_for('register'))
        
        users.append({
            'email': email,
            'password': generate_password_hash(password),
            'is_admin': False
        })
        save_json(USERS_FILE, {'users': users})
        
        flash('Cadastro realizado com sucesso!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        data = load_json(USERS_FILE)
        users = data.get('users', [])
        user = next((u for u in users if u['email'] == email), None)
        
        if user and check_password_hash(user['password'], password):
            session['user_email'] = email
            session['is_admin'] = user.get('is_admin', False)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin_panel' if user.get('is_admin') else 'index'))
        
        flash('Email ou senha incorretos', 'error')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso', 'success')
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_panel():
    data = load_json(PRODUCTS_FILE)
    products = data.get('products', [])
    return render_template('admin.html', products=products)

@app.route('/admin/adicionar', methods=['GET', 'POST'])
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        category = request.form.get('category')
        sizes = request.form.getlist('sizes')
        image = request.files.get('image')
        
        if not all([name, description, price, category, image]):
            flash('Preencha todos os campos', 'error')
            return redirect(url_for('add_product'))
        
        # Salvar imagem
        filename = secure_filename(image.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{timestamp}_{filename}"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)
        
        # Adicionar produto
        data = load_json(PRODUCTS_FILE)
        products = data.get('products', [])
        new_id = max([p['id'] for p in products], default=0) + 1
        
        products.append({
            'id': new_id,
            'name': name,
            'description': description,
            'price': float(price),
            'category': category,
            'sizes': sizes,
            'image': f"uploads/{filename}",
            'created_at': datetime.now().isoformat()
        })
        
        save_json(PRODUCTS_FILE, {'products': products})
        flash('Produto adicionado com sucesso!', 'success')
        return redirect(url_for('admin_panel'))
    
    return render_template('add_product.html')

@app.route('/admin/editar/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    data = load_json(PRODUCTS_FILE)
    products = data.get('products', [])
    product = next((p for p in products if p['id'] == product_id), None)
    
    if not product:
        flash('Produto não encontrado', 'error')
        return redirect(url_for('admin_panel'))
    
    if request.method == 'POST':
        product['name'] = request.form.get('name')
        product['description'] = request.form.get('description')
        product['price'] = float(request.form.get('price'))
        product['category'] = request.form.get('category')
        product['sizes'] = request.form.getlist('sizes')
        
        image = request.files.get('image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{filename}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            product['image'] = f"uploads/{filename}"
        
        save_json(PRODUCTS_FILE, {'products': products})
        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('admin_panel'))
    
    return render_template('edit_product.html', product=product)

@app.route('/admin/deletar/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    data = load_json(PRODUCTS_FILE)
    products = data.get('products', [])
    products = [p for p in products if p['id'] != product_id]
    save_json(PRODUCTS_FILE, {'products': products})
    flash('Produto deletado com sucesso!', 'success')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)