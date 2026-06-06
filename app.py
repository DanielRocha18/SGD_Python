import sys
sys.dont_write_bytecode = True
from flask import Flask, render_template, url_for, request, redirect, session, flash, Response, send_file, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from servicos import app, db
from servicos.model import *
from servicos.functions import *
from sqlalchemy import not_

#bloqueia cache de imagens
@app.after_request
def add_header(response):
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response

#cria rota principal 
@app.route('/')
def index():
    try:
        if current_user.is_authenticated:
            # Troque 'usuario.rendDashboardUsuario' por 'padrao.rendDashboardPadrao'
            return redirect(url_for('padrao.rendDashboardPadrao')) 
            
        return render_template('login.html')
    except Exception as e:
        return "Ocorreu um erro ao renderizar o sistema. Tente novamente mais tarde"

# --- SUBSTITUA A SUA ROTA DE LOGIN POR ESTAS DUAS ABAIXO ---

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        usuario_login = request.form.get('usuario')
        senha = request.form.get('senha')

        # Verificações básicas
        if Usuario.query.filter_by(nome_usuario=usuario_login).first():
            flash('Este nome de usuário já existe.', 'danger')
            return redirect(url_for('cadastro'))
            
        if Usuario.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado.', 'danger')
            return redirect(url_for('cadastro'))

        # Criar novo usuário (Perfil ID 4 geralmente é o 'Padrao' no seu banco)
        novo_usuario = Usuario(
            nome_usuario=usuario_login, 
            email=email,
            senha=senha, 
            perfil_id=4
        )
        
        # O 'nome' a gente atribui por fora
        novo_usuario.nome = nome
        
        # Criptografa a senha e salva
        novo_usuario.set_senha(senha)
        novo_usuario.ativo = True
        
        db.session.add(novo_usuario)
        db.session.commit()

        flash('Conta criada com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))

    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Troque aqui também!
        return redirect(url_for('padrao.rendDashboardPadrao')) 

    if request.method == 'POST':
        nome_usuario = request.form.get('usuario')
        senha = request.form.get('senha')

        user = Usuario.query.filter_by(nome_usuario=nome_usuario).first()

        if user and user.verificar_senha(senha):
            if user.ativo:
                login_user(user)
                # E troque aqui também!
                return redirect(url_for('padrao.rendDashboardPadrao')) 
            else:
                flash('Sua conta está desativada. Entre em contato com o suporte.', 'warning')
        else:
            flash('Usuário ou senha incorretos.', 'danger')

    return render_template('login.html')

@app.route('/primeiro_acesso', methods=['GET', 'POST'])
@login_required
def primeiro_acesso():
    try:
        if request.method == 'POST':
            # recupera dados do formulário
            matricula = request.form.get('matricula')
            nome_completo = request.form.get('nome_completo')
            telefone = request.form.get('telefone')
            unidade_lotacao = request.form.get('unidade_lotacao')
            unidade_lotacao_manual = request.form.get('unidade_lotacao_manual')
            login_rede = request.form.get('login_rede')
            
            # Define qual campo de unidade usar
            unidade_final = unidade_lotacao_manual if unidade_lotacao_manual else unidade_lotacao
            
            # Se tem matrícula, busca no banco corporativo
            cpf_servidor = None
            if matricula:
                matricula_clean = matricula.lstrip('0')
                servidor = db.session.query(Servidor).filter(
                    db.or_(
                        Servidor.matr == matricula,
                        Servidor.matr == matricula_clean,
                        Servidor.matr == matricula.zfill(9)  # Tenta com zeros à esquerda
                    )
                ).first()
                
                if servidor:
                    cpf_servidor = servidor.CPF
            
            # atualiza os dados do usuário (aceita valores vazios/None)
            current_user.nome = nome_completo if nome_completo else None
            current_user.cpf = cpf_servidor  
            current_user.matricula = matricula if matricula else None
            current_user.telefone = telefone if telefone else None
            current_user.unidade_lotacao = unidade_final if unidade_final else None
            current_user.login_rede = login_rede if login_rede else None
            
            db.session.commit()
            
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('padrao.rendDashboardPadrao'))
        
        # Obter grupos do usuário (para exibir no dropdown superior)
        if current_user.perfil.nome == 'Administrador':
            grupos_usuario = Grupo.query.filter(
                not_(Grupo.nome.like('__DEL__%'))
            ).order_by(Grupo.nome).all()
        else:
            # Correção com getattr para o perfil padrão não quebrar o menu
            grupos_usuario = getattr(current_user, 'grupos_tecnicos', [])
        
        # renderiza o formulário do perfil
        return render_template('primeiro_acesso.html', grupos_usuario=grupos_usuario)
        
    except Exception as e:
        flash(f'Erro ao processar perfil: {str(e)}', 'danger')
        return redirect(url_for('padrao.rendDashboardPadrao'))


# API para buscar dados do servidor por matrícula
@app.route('/api/buscar-servidor/<matricula>', methods=['GET'])
@login_required
def buscar_servidor(matricula):
    try:
        # Remove zeros à esquerda da matrícula para busca
        matricula_clean = matricula.lstrip('0')
        
        # Busca no banco corporativo
        servidor = db.session.query(Servidor).filter(
            db.or_(
                Servidor.matr == matricula,
                Servidor.matr == matricula_clean,
                Servidor.matr == matricula.zfill(9)  # Tenta com zeros à esquerda
            )
        ).first()
        
        if servidor:
            return jsonify({
                'success': True,
                'nome_completo': servidor.nome_servidor,
                'lotacao': servidor.lotacao_desc or servidor.lotacao,
                'cpf': servidor.CPF
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Matrícula {matricula} não encontrada no sistema.'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar dados: {str(e)}'
        })


# API para buscar lista de unidades/lotações
@app.route('/api/buscar-unidades', methods=['GET'])
@login_required
def buscar_unidades():
    try:
        # Busca todas as lotações únicas no banco corporativo
        unidades = db.session.query(
            Servidor.lotacao_desc
        ).filter(
            Servidor.lotacao_desc.isnot(None),
            Servidor.lotacao_desc != ''
        ).distinct().order_by(Servidor.lotacao_desc).all()
        
        # Converte para lista de strings
        lista_unidades = [u.lotacao_desc for u in unidades if u.lotacao_desc]
        
        return jsonify({
            'success': True,
            'unidades': lista_unidades
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar unidades: {str(e)}'
        })


@app.route('/deslogar')
@login_required
def deslogar():
    try:
        logout_user()
        return redirect(url_for('index'))
    except Exception as e:
        return f'Erro ao deslogar: {e}' 

#cria rota para desafio letsencrypt
@app.route('/.well-known/acme-challenge/<challenge>')
def letsencrypt_check(challenge):
    try:
        return send_file(f"static/.well-known/acme-challenge/{challenge}", attachment_filename=f'{challenge}')
    except Exception as e:
        return f"{e}"

#inicializa aplicacao
if __name__ == '__main__':
    app.run(debug=True)