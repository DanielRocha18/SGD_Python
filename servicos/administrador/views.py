from flask import render_template, url_for, request, redirect, Blueprint, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from servicos import db
from servicos.model import *
from sqlalchemy.exc import IntegrityError
from sqlalchemy import not_
import time

# Criação do Blueprint para as rotas de administrador
admin_blue = Blueprint('admin', __name__, template_folder='templates')


def admin_required(f):
    """
    Decorator personalizado para verificar se o usuário é administrador ou técnico_adm.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # Verifica se o usuário tem perfil de Administrador ou Tecnico_adm
        if not hasattr(current_user, 'perfil') or current_user.perfil.nome not in ['Administrador', 'Tecnico_adm']:
            flash('Acesso negado. Você não tem permissão de administrador.', 'danger')
            return redirect(url_for('padrao.rendDashboardPadrao'))
        return f(*args, **kwargs)
    return decorated_function

@admin_blue.route('/')
@admin_required
def rendDashboardAdmin():
    """
    Redireciona o painel principal de administração para a tela de Gerenciar Serviços.
    """
    # Se não for admin ou técnico_adm, joga pro painel padrão (segurança extra)
    if current_user.perfil.nome not in ['Administrador', 'Tecnico_adm', 'Tecnico']:
        return redirect(url_for('padrao.rendDashboardPadrao'))

    # Redireciona para a lista de serviços (Grupos)
    return redirect(url_for('admin.gerenciar_usuarios'))

@admin_blue.route('/usuarios', methods=['GET', 'POST'])
@admin_required
def gerenciar_usuarios():
    """Rota para gerenciar usuários (CRUD)."""
    from servicos.model import Usuario, Perfil
    
    if request.method == 'POST':
        try:
            # Pega dados do formulário
            user_id = request.form.get('user_id')
            login = request.form.get('login')
            perfil_id = request.form.get('perfil_id')
            ativo = request.form.get('ativo') == 'on'
            grupos_ids = request.form.getlist('grupos_ids')  # IDs dos grupos selecionados (múltiplos)
            
            # Gera o e-mail automaticamente baseado no login
            email = f"{login}@sejus.df.gov.br"
            
            if user_id:
                # Editar usuário existente
                usuario = Usuario.query.get_or_404(user_id)
                
                # VALIDAÇÃO: Se não for Administrador, verifica se o usuário pertence aos mesmos grupos
                if current_user.perfil.nome != 'Administrador':
                    grupos_do_tecnico = db.session.query(TecnicoGrupo.grupo_id).filter(
                        TecnicoGrupo.usuario_id == current_user.id
                    ).all()
                    grupos_do_tecnico_ids = [g[0] for g in grupos_do_tecnico]
                    
                    # Verifica se o usuário a ser editado está nos mesmos grupos
                    grupos_do_usuario = db.session.query(TecnicoGrupo.grupo_id).filter(
                        TecnicoGrupo.usuario_id == usuario.id
                    ).all()
                    grupos_do_usuario_ids = [g[0] for g in grupos_do_usuario]
                    
                    if not any(g in grupos_do_tecnico_ids for g in grupos_do_usuario_ids):
                        flash('Você não tem permissão para editar este usuário.', 'danger')
                        return redirect(url_for('admin.gerenciar_usuarios'))
                    
                    # Valida se os grupos selecionados pertencem ao técnico
                    for gid in grupos_ids:
                        if gid and int(gid) not in grupos_do_tecnico_ids:
                            flash('Você não tem permissão para atribuir um ou mais grupos selecionados.', 'danger')
                            return redirect(url_for('admin.gerenciar_usuarios'))
                
                usuario.email = email
                usuario.perfil_id = perfil_id
                usuario.ativo = ativo
                
                # Atualiza associações de grupos
                # Remove associações antigas
                TecnicoGrupo.query.filter_by(usuario_id=usuario.id).delete()
                
                # Adiciona novas associações (para cada grupo selecionado)
                for gid in grupos_ids:
                    if gid:  # Valida que não está vazio
                        nova_associacao = TecnicoGrupo(
                            usuario_id=usuario.id,
                            grupo_id=int(gid)
                        )
                        db.session.add(nova_associacao)
                
                db.session.commit()
                flash(f'Usuário {usuario.nome_usuario} atualizado com sucesso!', 'success')
            else:
                # Criar novo usuário
                if not perfil_id:
                    flash('Erro: Selecione um perfil para o novo usuário.', 'danger')
                    return redirect(url_for('admin.gerenciar_usuarios'))
                
                # VALIDAÇÃO: Se não for Administrador, valida se os grupos pertencem ao técnico
                if current_user.perfil.nome != 'Administrador':
                    if grupos_ids:
                        grupos_do_tecnico = db.session.query(TecnicoGrupo.grupo_id).filter(
                            TecnicoGrupo.usuario_id == current_user.id
                        ).all()
                        grupos_do_tecnico_ids = [g[0] for g in grupos_do_tecnico]
                        
                        for gid in grupos_ids:
                            if gid and int(gid) not in grupos_do_tecnico_ids:
                                flash('Você não tem permissão para atribuir um ou mais grupos selecionados.', 'danger')
                                return redirect(url_for('admin.gerenciar_usuarios'))
                
                novo_usuario = Usuario(
                    nome_usuario=login,
                    email=email,
                    perfil_id=perfil_id,
                    ativo=ativo
                )
                db.session.add(novo_usuario)
                db.session.flush()  # Garante que o ID seja gerado antes de associar grupos
                
                # Adiciona associações de grupos (para cada grupo selecionado)
                for gid in grupos_ids:
                    if gid:  # Valida que não está vazio
                        nova_associacao = TecnicoGrupo(
                            usuario_id=novo_usuario.id,
                            grupo_id=int(gid)
                        )
                        db.session.add(nova_associacao)
                
                db.session.commit()
                flash(f'Usuário {login} criado com sucesso!', 'success')
            
            return redirect(url_for('admin.gerenciar_usuarios'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar usuário: {str(e)}', 'danger')
            return redirect(url_for('admin.gerenciar_usuarios'))
    
    # GET - Listar usuários
    try:
        # Pega o termo de busca
        search_query = request.args.get('q', '').strip()
        
        # Query base
        query = Usuario.query
        
        # FILTRO POR GRUPO: Se não for Administrador, mostra apenas usuários dos mesmos grupos
        if current_user.perfil.nome != 'Administrador':
            # Busca os grupos do usuário atual
            grupos_do_usuario = db.session.query(TecnicoGrupo.grupo_id).filter(
                TecnicoGrupo.usuario_id == current_user.id
            ).subquery()
            
            # Busca IDs de usuários que pertencem aos mesmos grupos
            usuarios_mesmos_grupos = db.session.query(TecnicoGrupo.usuario_id).filter(
                TecnicoGrupo.grupo_id.in_(grupos_do_usuario)
            ).distinct().subquery()
            
            # Filtra apenas usuários dos mesmos grupos
            query = query.filter(Usuario.id.in_(usuarios_mesmos_grupos))
        
        # Aplica filtro de busca se houver
        if search_query:
            query = query.filter(
                db.or_(
                    Usuario.nome_usuario.ilike(f'%{search_query}%'),
                    Usuario.email.ilike(f'%{search_query}%'),
                    Usuario.nome.ilike(f'%{search_query}%')
                )
            )
        
        usuarios = query.all()
        
        # Adiciona lista de grupos para cada usuário
        for usuario in usuarios:
            grupos_associados = db.session.query(TecnicoGrupo.grupo_id).filter(
                TecnicoGrupo.usuario_id == usuario.id
            ).all()
            usuario.grupos_ids = [g[0] for g in grupos_associados]
        
        perfis = Perfil.query.all()
        
        # Busca grupos ativos (exclui grupos marcados como deletados)
        if current_user.perfil.nome == 'Administrador':
            # Administrador vê todos os grupos
            grupos = Grupo.query.filter(not_(Grupo.nome.like('__DEL__%'))).order_by(Grupo.nome).all()
        else:
            # Técnicos veem apenas seus grupos
            grupos = db.session.query(Grupo).join(
                TecnicoGrupo, Grupo.id == TecnicoGrupo.grupo_id
            ).filter(
                TecnicoGrupo.usuario_id == current_user.id,
                not_(Grupo.nome.like('__DEL__%'))
            ).order_by(Grupo.nome).all()
        
        # Obter grupos do usuário (para exibir no dropdown)
        grupos_usuario = Grupo.query.filter(
            not_(Grupo.nome.like('__DEL__%'))
        ).order_by(Grupo.nome).all()
        
        return render_template('usuarios.html', 
                             titulo_pagina="Gerenciar Usuários", 
                             usuarios=usuarios, 
                             perfis=perfis,
                             grupos=grupos,
                             grupos_usuario=grupos_usuario,
                             search_query=search_query)
    except Exception as e:
        flash(f'Erro ao carregar usuários: {str(e)}', 'danger')
        grupos_usuario = Grupo.query.filter(not_(Grupo.nome.like('__DEL__%'))).order_by(Grupo.nome).all()
        return render_template('usuarios.html', titulo_pagina="Gerenciar Usuários", usuarios=[], perfis=[], grupos=[], grupos_usuario=grupos_usuario)

@admin_blue.route('/agendas')
@admin_required
def gerenciar_agendas():
    """Rota para gerenciar agendamentos/disponibilidade."""
    # Adicionar lógica de consulta de agendas aqui se necessário
    return render_template('admin/agendas.html', titulo_pagina="Gerenciar Agendas")

@admin_blue.route('/usuario/<int:usuario_id>/ativar', methods=['POST'])
@admin_required
def ativar_usuario(usuario_id):
    """Rota para ativar um usuário."""
    from servicos.model import Usuario
    try:
        usuario = Usuario.query.get_or_404(usuario_id)
        usuario.ativo = True
        db.session.commit()
        flash(f'Usuário {usuario.nome_usuario} ativado com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao ativar usuário: {str(e)}', 'danger')
    return redirect(url_for('admin.gerenciar_usuarios')) 

@admin_blue.route('/usuario/<int:usuario_id>/desativar', methods=['POST'])
@admin_required 
def desativar_usuario(usuario_id):
    """Rota para desativar um usuário."""
    from servicos.model import Usuario
    try:
        usuario = Usuario.query.get_or_404(usuario_id)
        usuario.ativo = False
        db.session.commit()
        flash(f'Usuário {usuario.nome_usuario} desativado com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao desativar usuário: {str(e)}', 'danger')
    return redirect(url_for('admin.gerenciar_usuarios'))

@admin_blue.route('/servicos')
@admin_required
def gerenciar_servicos():
    from servicos.model import Grupo 
    
    # Prefixo que identifica itens excluídos
    PREFIXO_DEL = "__DEL__"

    # Lógica Tecnico_adm
    if current_user.perfil.nome == 'Tecnico_adm':
        grupo_padrao = Grupo.query.filter(
            Grupo.nome.ilike('%Suporte Informática%'),
            not_(Grupo.nome.startswith(PREFIXO_DEL)) # <--- FILTRO: NÃO COMEÇA COM __DEL__
        ).first()
        
        if not grupo_padrao:
            # Fallback: pega o primeiro que não esteja deletado
            grupo_padrao = Grupo.query.filter(not_(Grupo.nome.startswith(PREFIXO_DEL))).first()
            
        if grupo_padrao:
            return redirect(url_for('admin.gerenciar_grupo_detalhes', grupo_id=grupo_padrao.id))
        else:
            flash('Nenhum grupo de serviço ativo encontrado.', 'warning')
            return redirect(url_for('padrao.rendDashboardPadrao'))

    # Lógica Administrador: Lista apenas grupos que NÃO começam com o prefixo
    grupos = Grupo.query.filter(not_(Grupo.nome.startswith(PREFIXO_DEL))).order_by(Grupo.nome).all()
    
    # Obter grupos do usuário (para exibir no dropdown)
    grupos_usuario = Grupo.query.filter(
        not_(Grupo.nome.like('__DEL__%'))
    ).order_by(Grupo.nome).all()
    
    return render_template('servicos.html', grupos=grupos, grupos_usuario=grupos_usuario, titulo_pagina="Gerenciar Grupos de Serviço")


@admin_blue.route('/servicos/grupo/<int:grupo_id>')
@admin_required
def gerenciar_grupo_detalhes(grupo_id):
    from servicos.model import Grupo, Categoria, Item
    
    PREFIXO_DEL = "__DEL__"
    grupo = Grupo.query.get_or_404(grupo_id)
    
    # 1. Busca Categorias (filtrando as deletadas)
    categorias = Categoria.query.filter(
        Categoria.grupo_id == grupo.id,
        not_(Categoria.nome.startswith(PREFIXO_DEL)) # <--- FILTRO AQUI
    ).order_by(Categoria.nome).all()
    
    cat_selecionada_id = request.args.get('cat_id', type=int)
    categoria_selecionada = None
    itens = []
    
    if cat_selecionada_id:
        categoria_selecionada = Categoria.query.get(cat_selecionada_id)
        
        # Verifica validade e se não está "deletada"
        if (categoria_selecionada and 
            categoria_selecionada.grupo_id == grupo.id and 
            not categoria_selecionada.nome.startswith(PREFIXO_DEL)):
            
            # 2. Busca Itens (filtrando os deletados)
            itens = Item.query.filter(
                Item.categoria_id == categoria_selecionada.id,
                not_(Item.nome.startswith(PREFIXO_DEL)) # <--- FILTRO AQUI
            ).order_by(Item.nome).all()
        else:
            categoria_selecionada = None
            
    # Obter grupos do usuário (para exibir no dropdown)
    grupos_usuario = Grupo.query.filter(
        not_(Grupo.nome.like('__DEL__%'))
    ).order_by(Grupo.nome).all()
    
    return render_template('categorias_itens.html', 
                         grupo=grupo, 
                         categorias=categorias, 
                         categoria_selecionada=categoria_selecionada,
                         itens=itens,
                         grupos_usuario=grupos_usuario,
                         titulo_pagina=f"Gerenciar: {grupo.nome}")

@admin_blue.route('/servicos/grupo/<int:grupo_id>/deletar', methods=['POST'])
@admin_required
def deletar_grupo(grupo_id):
    if current_user.perfil.nome != 'Administrador':
        flash('Permissão negada.', 'danger')
        return redirect(url_for('admin.gerenciar_servicos'))

    from servicos.model import Grupo
    grupo = Grupo.query.get_or_404(grupo_id)
    
    try:
        # DELETE LÓGICO VIA NOME (Para não quebrar chave única)
        # Ex: "Suporte" vira "__DEL__17356622__Suporte"
        timestamp = int(time.time())
        grupo.nome = f"__DEL__{timestamp}__{grupo.nome}"
        
        # Opcional: Ocultar filhos também para garantir
        # for cat in grupo.categorias:
        #     cat.nome = f"__DEL__{timestamp}__{cat.nome}"
        
        db.session.commit()
        flash('Grupo removido com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover: {str(e)}', 'danger')

    return redirect(url_for('admin.gerenciar_servicos'))


@admin_blue.route('/servicos/categoria/<int:categoria_id>/deletar', methods=['POST'])
@admin_required
def deletar_categoria(categoria_id):
    from servicos.model import Categoria
    categoria = Categoria.query.get_or_404(categoria_id)
    grupo_id = categoria.grupo_id
    
    try:
        timestamp = int(time.time())
        # Renomeia para ocultar
        categoria.nome = f"__DEL__{timestamp}__{categoria.nome}"
        
        db.session.commit()
        flash('Categoria removida com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover: {str(e)}', 'danger')
    
    return redirect(url_for('admin.gerenciar_grupo_detalhes', grupo_id=grupo_id))


@admin_blue.route('/servicos/item/<int:item_id>/deletar', methods=['POST'])
@admin_required
def deletar_item(item_id):
    from servicos.model import Item
    item = Item.query.get_or_404(item_id)
    grupo_id = item.categoria.grupo_id
    categoria_id = item.categoria_id
    
    try:
        timestamp = int(time.time())
        # Renomeia para ocultar
        item.nome = f"__DEL__{timestamp}__{item.nome}"
        
        db.session.commit()
        flash('Serviço removido com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover: {str(e)}', 'danger')
    
    return redirect(url_for('admin.gerenciar_grupo_detalhes', grupo_id=grupo_id, cat_id=categoria_id))

@admin_blue.route('/servicos/grupo/salvar', methods=['POST'])
@admin_required
def salvar_grupo():
    from servicos.model import Grupo
    
    if current_user.perfil.nome != 'Administrador':
        flash('Permissão negada.', 'danger')
        return redirect(url_for('admin.gerenciar_servicos'))

    try:
        grupo_id = request.form.get('grupo_id')
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        
        # VERIFIQUE SE ESTA LINHA EXISTE:
        cor_borda = request.form.get('cor_borda', '#4e73df')
        icone = request.form.get('icone', 'fas fa-folder')
        emprestimo_ativo = request.form.get('emprestimo_ativo') == '1'
        
        # DEBUG
        print(f"DEBUG salvar_grupo - ID: {grupo_id}, Nome: {nome}, Cor: {cor_borda}, Empréstimo: {emprestimo_ativo}")

        if grupo_id:
            grupo = Grupo.query.get_or_404(grupo_id)
            grupo.nome = nome
            grupo.descricao = descricao
            
            # VERIFIQUE SE ESTA LINHA EXISTE:
            grupo.cor_borda = cor_borda 
            grupo.icone = icone
            grupo.emprestimo_ativo = emprestimo_ativo
            
            msg = 'Grupo atualizado com sucesso!'
        else:
            # E AQUI TAMBÉM:
            grupo = Grupo(nome=nome, descricao=descricao, cor_borda=cor_borda, icone=icone, emprestimo_ativo=emprestimo_ativo)
            db.session.add(grupo)
            msg = 'Grupo criado com sucesso!'
        
        db.session.commit()
        flash(msg, 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar grupo: {str(e)}', 'danger')

    return redirect(url_for('admin.gerenciar_servicos'))


@admin_blue.route('/servicos/categoria/salvar', methods=['POST'])
@admin_required
def salvar_categoria():
    from servicos.model import Categoria
    
    grupo_id = request.form.get('grupo_id') # Movido para fora do try para garantir acesso no except
    
    try:
        categoria_id = request.form.get('categoria_id')
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        cor_borda = request.form.get('cor_borda', '#36b9cc')
        icone = request.form.get('icone', 'fas fa-folder-open')

        if categoria_id:
            cat = Categoria.query.get_or_404(categoria_id)
            cat.nome = nome
            cat.descricao = descricao
            cat.cor_borda = cor_borda
            cat.icone = icone
            msg = 'Categoria atualizada!'
        else:
            cat = Categoria(grupo_id=grupo_id, nome=nome, descricao=descricao, cor_borda=cor_borda, icone=icone)
            db.session.add(cat)
            msg = 'Categoria criada!'
        
        db.session.commit()
        flash(msg, 'success')
        
        cat_id_redirect = cat.id if cat else None
        return redirect(url_for('admin.gerenciar_grupo_detalhes', grupo_id=grupo_id, cat_id=cat_id_redirect))
        
    except IntegrityError:
        db.session.rollback()
        flash(f'Erro: Já existe uma categoria com o nome "{nome}" neste grupo.', 'warning')
        return redirect(url_for('admin.gerenciar_grupo_detalhes', grupo_id=grupo_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar categoria: {str(e)}', 'danger')
        return redirect(url_for('admin.gerenciar_grupo_detalhes', grupo_id=grupo_id))


@admin_blue.route('/servicos/item/salvar', methods=['POST'])
@admin_required
def salvar_item():
    from servicos.model import Item
    
    grupo_id = request.form.get('grupo_id')
    categoria_id = request.form.get('categoria_id')
    
    try:
        item_id = request.form.get('item_id')
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        cor_borda = request.form.get('cor_borda', '#1cc88a')
        icone = request.form.get('icone', 'fas fa-cube')

        if item_id:
            item = Item.query.get_or_404(item_id)
            item.nome = nome
            item.descricao = descricao
            item.cor_borda = cor_borda
            item.icone = icone
            msg = 'Item atualizado!'
        else:
            item = Item(categoria_id=categoria_id, nome=nome, descricao=descricao, cor_borda=cor_borda, icone=icone)
            db.session.add(item)
            msg = 'Item criado!'
        
        db.session.commit()
        flash(msg, 'success')
        return redirect(url_for('admin.gerenciar_grupo_detalhes', grupo_id=grupo_id, cat_id=categoria_id))

    except IntegrityError:
        db.session.rollback()
        flash(f'Erro: Já existe um serviço com o nome "{nome}" nesta categoria.', 'warning')
        return redirect(url_for('admin.gerenciar_grupo_detalhes', grupo_id=grupo_id, cat_id=categoria_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar item: {str(e)}', 'danger')
        if grupo_id:
            return redirect(url_for('admin.gerenciar_grupo_detalhes', grupo_id=grupo_id, cat_id=categoria_id))
        return redirect(url_for('admin.gerenciar_servicos'))
    
@admin_blue.route('/formularios')
@admin_required
def gerenciar_formularios():
    from servicos.model import Formulario, Item, Categoria, Grupo
    from sqlalchemy import not_
    
    # Busca formulários
    formularios = Formulario.query.order_by(Formulario.titulo).all()
    
    # CORREÇÃO: Busca Itens filtrando se ELE, a CATEGORIA ou o GRUPO estão deletados
    itens = db.session.query(Item).join(Categoria).join(Grupo).filter(
        not_(Item.nome.startswith('__DEL__')),      # Item não deletado
        not_(Categoria.nome.startswith('__DEL__')), # Categoria não deletada
        not_(Grupo.nome.startswith('__DEL__'))      # Grupo não deletado
    ).order_by(Item.nome).all()
    
    return render_template('formularios.html', 
                         formularios=formularios, 
                         itens=itens,
                         titulo_pagina="Gerenciar Formulários")

@admin_blue.route('/formularios/salvar', methods=['POST'])
@admin_required
def salvar_formulario():
    try:
        # Importações necessárias
        from servicos.model import Formulario, CampoFormulario
        
        form_id = request.form.get('formulario_id')
        titulo = request.form.get('titulo')
        item_id = request.form.get('item_id')
        ativo = request.form.get('ativo') == 'on'
        
        # Listas dos campos (Vem como array do HTML)
        labels = request.form.getlist('campo_label[]')
        tipos = request.form.getlist('campo_tipo[]')
        
        if form_id:
            # --- MODO EDIÇÃO ---
            formulario = Formulario.query.get_or_404(form_id)
            formulario.titulo = titulo
            formulario.item_id = item_id
            formulario.ativo = ativo
            
            # 1. Remove campos antigos (Hard Delete dos filhos para recriar)
            # Isso é mais seguro que tentar atualizar um por um
            CampoFormulario.query.filter_by(formulario_id=formulario.id).delete()
            
            msg = 'Formulário atualizado com sucesso!'
        else:
            # --- MODO CRIAÇÃO ---
            formulario = Formulario(titulo=titulo, item_id=item_id, ativo=ativo)
            db.session.add(formulario)
            msg = 'Formulário criado com sucesso!'
        
        # Salva o formulário pai (e a deleção dos filhos se for edição)
        db.session.commit()
        
        # 2. Adiciona os novos campos
        if labels and len(labels) > 0:
            for i, label in enumerate(labels):
                if label and label.strip(): # Ignora campos vazios
                    tipo_campo = tipos[i] if i < len(tipos) else 'text'
                    
                    novo_campo = CampoFormulario(
                        formulario_id=formulario.id,
                        label=label.strip(),
                        tipo=tipo_campo,
                        ordem=i,
                        obrigatorio=False # Ajuste se tiver checkbox de obrigatório no futuro
                    )
                    db.session.add(novo_campo)
            
            db.session.commit() # Salva os filhos
            
        flash(msg, 'success')
        
    except Exception as e:
        db.session.rollback()
        # Log para debug no terminal
        print(f"ERRO AO SALVAR FORMULÁRIO: {e}")
        flash(f'Erro ao salvar formulário: {str(e)}', 'danger')

    return redirect(url_for('admin.gerenciar_formularios'))

# API para buscar detalhes do formulário (para edição)
@admin_blue.route('/api/formulario/<int:form_id>')
@login_required
def api_get_formulario(form_id):
    try:
        # Importe aqui para garantir que não dê erro
        from servicos.model import Formulario
        
        form = Formulario.query.get_or_404(form_id)
        
        # Monta a lista de campos para o JSON
        campos_lista = []
        for campo in form.campos:
            campos_lista.append({
                'id': campo.id,
                'label': campo.label,
                'tipo': campo.tipo,
                'obrigatorio': campo.obrigatorio,
                'ordem': campo.ordem
            })
            
        # Ordena os campos pela ordem de criação/definição
        campos_lista.sort(key=lambda x: x['ordem'])

        return jsonify({
            'id': form.id,
            'titulo': form.titulo,
            'item_id': form.item_id,
            'ativo': form.ativo,
            'campos': campos_lista
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@admin_blue.route('/formularios/deletar/<int:form_id>', methods=['POST'])
@admin_required
def deletar_formulario(form_id):
    try:
        # Importação local para garantir
        from servicos.model import Formulario
        
        formulario = Formulario.query.get_or_404(form_id)
        db.session.delete(formulario)
        db.session.commit()
        flash('Formulário excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir formulário: {e}', 'danger')
        
    return redirect(url_for('admin.gerenciar_formularios'))
