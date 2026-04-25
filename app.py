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
        return render_template('login.html')
    except Exception as e:
    #    return "retorna pagina de erro aqui"
        return "Ocorreu um erro ao renderizar o sistema. Tente novamente mais tarde"


#cria rota principal 
@app.route('/manual')
def manual():
    try:
        return render_template('manualtelefonia.html')
    except Exception as e:
    #    return "retorna pagina de erro aqui"
        return "Ocorreu um erro ao renderizar o sistema. Tente novamente mais tarde"


#funcao de login
@app.route('/login', methods=['POST'])
def login():
    try:
        # recupera atributos do form
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')

        # tenta o login pelo ldap
        try:
            Usuario.tentar_login(usuario, senha)
        except:
            flash('Usuário ou senha incorretos')
            return redirect(url_for('index'))

        # verifica se usuario já está cadastrado
        usuarioP = db.session.query(Usuario).filter(Usuario.nome_usuario == usuario).first()
        
        if usuarioP:
            # verifica se o usuário está ativo
            if not usuarioP.ativo:
                flash('Usuário inativo. Entre em contato com o administrador.')
                return redirect(url_for('index'))
            
            login_user(usuarioP)
            log(current_user.nome_usuario, f"Efetuou login no sistema")
            
            # verifica se o cadastro está completo (apenas o nome é obrigatório)
            if not usuarioP.nome:
                # redireciona para completar o cadastro
                return redirect(url_for('primeiro_acesso'))
        else:
            # cria novo usuário com perfil padrão
            perfil_padrao = db.session.query(Perfil).filter(Perfil.nome == 'Padrao').first()
            if not perfil_padrao:
                # se não existir o perfil padrão, cria
                perfil_padrao = Perfil(nome='Padrao')
                db.session.add(perfil_padrao)
                db.session.commit()
                
            # cria o usuário apenas com os dados essenciais
            usuarioC = Usuario(
                nome_usuario=usuario,
                email=f"{usuario}@sejus.df.gov.br",
                perfil_id=perfil_padrao.id,
                ativo=True
            )
            db.session.add(usuarioC)
            db.session.commit()
            db.session.refresh(usuarioC)
            login_user(usuarioC)
            log(current_user.nome_usuario, f"Primeiro acesso ao sistema")
            
            # redireciona para completar o cadastro
            return redirect(url_for('primeiro_acesso'))
       
        log(current_user.nome_usuario, f"Efetuou login no sistema")

        # redireciona para o dashboard correto baseado no perfil
        perfil_nome = current_user.perfil.nome
        
        if perfil_nome == 'Administrador':
            return redirect(url_for('padrao.rendDashboardPadrao'))
        elif perfil_nome == 'Tecnico' or perfil_nome == 'Tecnico_adm':
            return redirect(url_for('tecnico.gerenciamento_demandas'))
        elif perfil_nome == 'Padrao':
            return redirect(url_for('padrao.rendDashboardPadrao'))
        else:
            # fallback para usuário padrão
            return redirect(url_for('padrao.rendDashboardPadrao'))
            
    except Exception as e:
        flash(f'Erro no login: {str(e)}')
        return redirect(url_for('index'))



# rota para primeiro acesso
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
            current_user.cpf = cpf_servidor  # Pode ser None se não tem matrícula
            current_user.matricula = matricula if matricula else None
            current_user.telefone = telefone if telefone else None
            current_user.unidade_lotacao = unidade_final if unidade_final else None
            current_user.login_rede = login_rede if login_rede else None
            
            db.session.commit()
            log(current_user.nome_usuario, f"Completou o cadastro de primeiro acesso")
            
            # Redireciona sempre para o dashboard padrão após atualizar perfil
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('padrao.rendDashboardPadrao'))
        
        # Obter grupos do usuário (para exibir no dropdown)
        if current_user.perfil.nome == 'Administrador':
            grupos_usuario = Grupo.query.filter(
                not_(Grupo.nome.like('__DEL__%'))
            ).order_by(Grupo.nome).all()
        else:
            grupos_usuario = current_user.grupos_tecnicos
        
        # renderiza o formulário de primeiro acesso
        return render_template('primeiro_acesso.html', grupos_usuario=grupos_usuario)
        
    except Exception as e:
        flash(f'Erro ao processar primeiro acesso: {str(e)}')
        grupos_usuario = current_user.grupos_tecnicos if hasattr(current_user, 'grupos_tecnicos') else []
        return render_template('primeiro_acesso.html', grupos_usuario=grupos_usuario)


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