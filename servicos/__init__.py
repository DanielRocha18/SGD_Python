# coding: utf-8
import os 
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager 
from dotenv import load_dotenv

#recupera variaveis de ambiente
if os.environ.get('USERNAME'):
    load_dotenv()
else:
    path = "/var/www/central/.env"
    load_dotenv(dotenv_path=path, verbose=True)

#cria aplicativo web e objeto do banco
app = Flask(__name__) 
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("CONEXAO_DB")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_BINDS'] = {'corporativo':os.environ.get("CONEXAO_DB2")}

upload_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads')
app.config['UPLOAD_FOLDER'] = upload_path
os.makedirs(upload_path, exist_ok=True) 
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

db = SQLAlchemy(app)

#configuracoes flask login
loginManager = LoginManager()
loginManager.login_view = 'index'
loginManager.login_message = 'Você precisa estar logado para acessar essa página'
loginManager.init_app(app)
from .model import Usuario
@loginManager.user_loader
def load_user(user_id):
    return Usuario.query.get(user_id)

#definicao da secret_key
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")

#definicao do banco de dados

#cria banco de dados
from servicos.model import *
with app.app_context():
    # Cria todas as tabelas (principal e corporativo)
    db.create_all()
    
    # Cria perfis padrão se não existirem
    perfis_padrao = ['Padrao', 'Tecnico', 'Tecnico_adm', 'Administrador']
    for nome_perfil in perfis_padrao:
        perfil_existe = db.session.query(Perfil).filter(Perfil.nome == nome_perfil).first()
        if not perfil_existe:
            novo_perfil = Perfil(nome=nome_perfil)
            db.session.add(novo_perfil)
            print(f"✓ Perfil '{nome_perfil}' criado no banco de dados")
    
    # Cria status padrão se não existirem
    # ORDEM IMPORTANTE: O código usa IDs fixos (1=Aberto, 2=Em Andamento, 3=Finalizado, 4=Cancelado, 5=Reaberto, 6=Suspensa)
    status_padrao = ['Aberto', 'Em Andamento', 'Finalizado', 'Cancelado', 'Reaberto', 'Suspensa']
    for nome_status in status_padrao:
        status_existe = db.session.query(Status).filter(Status.nome == nome_status).first()
        if not status_existe:
            novo_status = Status(nome=nome_status)
            db.session.add(novo_status)
            print(f"✓ Status '{nome_status}' criado no banco de dados")
    
    db.session.commit()

#criacao dos blueprints
from servicos.usuario.views import usuario_blue
from servicos.padrao.views import padrao_blue
from servicos.tecnico.views import tecnico_blue
from servicos.administrador.views import admin_blue

app.register_blueprint(usuario_blue, url_prefix="/usuario")
app.register_blueprint(padrao_blue, url_prefix="/padrao")
app.register_blueprint(tecnico_blue, url_prefix="/tecnico")
app.register_blueprint(admin_blue, url_prefix="/admin")

