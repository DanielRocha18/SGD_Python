from flask import render_template, url_for, request, redirect, session, Blueprint, flash, jsonify, current_app
from flask_login import login_required, current_user
from servicos.model import * 
from servicos.functions import *
from servicos import app, db
from sqlalchemy.orm import joinedload
from datetime import datetime
from sqlalchemy import not_
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv', 'zip', 'rar'}

# Cria blueprint do tecnico
tecnico_blue = Blueprint('tecnico', __name__, template_folder='templates')

@tecnico_blue.route('/gerenciamento-demandas')
@login_required
def gerenciamento_demandas():
    try:
        # Pegar o grupo_id da URL (OBRIGATÓRIO)
        grupo_id = request.args.get('grupo_id', type=int)
        
        # Buscar grupos do usuário (Administrador vê TODOS os grupos)
        if current_user.perfil.nome == 'Administrador':
            grupos_usuario = Grupo.query.filter(
                not_(Grupo.nome.like('__DEL__%'))
            ).order_by(Grupo.nome).all()
        else:
            grupos_usuario = db.session.query(Grupo).join(
                TecnicoGrupo, Grupo.id == TecnicoGrupo.grupo_id
            ).filter(
                TecnicoGrupo.usuario_id == current_user.id
            ).all()
        
        # Se não tiver grupo_id na URL, redirecionar para o primeiro grupo
        if not grupo_id:
            if grupos_usuario:
                return redirect(url_for('tecnico.gerenciamento_demandas', grupo_id=grupos_usuario[0].id))
            else:
                flash('Você não está associado a nenhum grupo. Entre em contato com o administrador.', 'warning')
                return redirect(url_for('padrao.rendDashboardPadrao'))
        
        # Validar se o usuário pertence ao grupo solicitado (Administrador pode ver todos)
        if current_user.perfil.nome != 'Administrador':
            if not db.session.query(TecnicoGrupo).filter(
                TecnicoGrupo.usuario_id == current_user.id,
                TecnicoGrupo.grupo_id == grupo_id
            ).first():
                flash('Você não tem permissão para acessar esse grupo.', 'warning')
                return redirect(url_for('tecnico.gerenciamento_demandas', grupo_id=grupos_usuario[0].id))
        
        # Regra de Negócio: Técnico vê APENAS chamados do grupo selecionado
        # APENAS: Aberto (1), Em Andamento (2), Reaberto (5), Suspensa (6)
        # EXCLUIR: Finalizado (3) e Cancelado (4)
        query = Chamado.query.options(
            joinedload(Chamado.status),
            joinedload(Chamado.solicitante).joinedload(Usuario.perfil),
            joinedload(Chamado.subcategoria).joinedload(Categoria.grupo),
            joinedload(Chamado.tecnico_responsavel)
        ).join(
            Categoria, Chamado.subcategoria_id == Categoria.id
        ).join(
            Grupo, Categoria.grupo_id == Grupo.id
        ).filter(
            Chamado.status_id.in_([1, 2, 5, 6]),
            Categoria.grupo_id == grupo_id,
            # FILTRO DE DELETE LÓGICO:
            not_(Grupo.nome.startswith('__DEL__')),
            not_(Categoria.nome.startswith('__DEL__'))
        )
        
        # Aplicar filtros de pesquisa
        ticket_filtro = request.args.get('ticket', '').strip()
        status_filtro = request.args.get('status', '').strip()
        solicitante_filtro = request.args.get('solicitante', '').strip()
        atendente_filtro = request.args.get('atendente', '').strip()
        detalhamento_filtro = request.args.get('detalhamento', '').strip()
        servico_filtro = request.args.get('servico', '').strip()
        
        if ticket_filtro:
            try:
                # Tentar extrair ID do formato "123-2025"
                if '-' in ticket_filtro:
                    ticket_id = ticket_filtro.split('-')[0]
                    query = query.filter(Chamado.id == int(ticket_id))
                else:
                    query = query.filter(Chamado.id == int(ticket_filtro))
            except ValueError:
                pass  # Ignora se não for número válido
        
        if status_filtro:
            query = query.filter(Chamado.status_id == int(status_filtro))
        
        if solicitante_filtro:
            query = query.filter(
                db.or_(
                    Chamado.solicitante.has(Usuario.nome.ilike(f'%{solicitante_filtro}%')),
                    Chamado.solicitante.has(Usuario.nome_usuario.ilike(f'%{solicitante_filtro}%'))
                )
            )
        
        if atendente_filtro:
            query = query.filter(
                Chamado.tecnico_responsavel.has(Usuario.nome_usuario.ilike(f'%{atendente_filtro}%'))
            )
        
        if detalhamento_filtro:
            query = query.filter(
                db.or_(
                    Chamado.descricao.ilike(f'%{detalhamento_filtro}%'),
                    Chamado.titulo.ilike(f'%{detalhamento_filtro}%')
                )
            )
        
        if servico_filtro:
            query = query.filter(Chamado.titulo.ilike(f'%{servico_filtro}%'))
        
        # Ordena por data (mais recentes primeiro)
        demandas = query.order_by(Chamado.data_abertura.desc()).all()

        # Contadores reais do banco (apenas do grupo selecionado)
        base_count_query = Chamado.query.join(
            Categoria, Chamado.subcategoria_id == Categoria.id
        ).filter(
            Categoria.grupo_id == grupo_id
        )
        
        contadores = {
            'aberta': base_count_query.filter(Chamado.status_id == 1).count(), 
            'atendimento': base_count_query.filter(Chamado.status_id == 2).count(),
            'suspensa': base_count_query.filter(Chamado.status_id == 6).count(),
        }

        # Buscar técnicos do grupo atual para o modal de atribuição
        tecnicos_ids = db.session.query(TecnicoGrupo.usuario_id).filter(
            TecnicoGrupo.grupo_id == grupo_id
        ).distinct().subquery()
        
        tecnicos = Usuario.query.join(Perfil).filter(
            Perfil.nome.in_(['Tecnico', 'Tecnico_adm', 'Administrador']),
            Usuario.id.in_(tecnicos_ids)
        ).order_by(Usuario.nome_usuario).all()
        
        # Buscar todos os grupos disponíveis para transferência (excluir deletados)
        grupos_disponiveis = Grupo.query.filter(
            not_(Grupo.nome.like('__DEL__%'))
        ).order_by(Grupo.nome).all()
        
        # Paginação vazia (não implementada ainda)
        pagination = {'pages': 0}
        
        # Buscar o grupo atualmente selecionado
        grupo_atual = Grupo.query.get(grupo_id)

        return render_template('gerenciamento_demandas.html', 
                               demandas=demandas, 
                               contadores=contadores,
                               tecnicos=tecnicos,
                               grupos_disponiveis=grupos_disponiveis,
                               grupos_usuario=grupos_usuario,
                               grupo_atual=grupo_atual,
                               pagination=pagination,
                               titulo_pagina="Painel do Técnico")

    except Exception as e:
        flash(f'Erro ao carregar demandas: {e}', 'danger')
        return redirect(url_for('index'))

@tecnico_blue.route('/atendimento/<int:chamado_id>')
@login_required
def atendimento_chamado(chamado_id):
    try:
        # Busca o chamado com todas as conexões necessárias
        chamado = Chamado.query.options(
            joinedload(Chamado.solicitante),
            joinedload(Chamado.subcategoria).joinedload(Categoria.grupo),
            joinedload(Chamado.status),
            joinedload(Chamado.tecnico_responsavel),
            joinedload(Chamado.chamado_pai)
        ).get_or_404(chamado_id)

        # Busca o histórico do chamado ordenado por data (mais recente primeiro)
        historicos = HistoricoChamado.query.options(
            joinedload(HistoricoChamado.usuario)
        ).filter_by(chamado_id=chamado_id).order_by(HistoricoChamado.data_interacao.desc()).all()

        solicitante = chamado.solicitante

        # Monta o título do Ticket (ID + Ano)
        ano_chamado = chamado.data_abertura.year
        titulo = f" Nº: {chamado.id}-{ano_chamado} - {chamado.status.nome}"
        
        if chamado.tecnico_responsavel:
             nome_tecnico = chamado.tecnico_responsavel.nome or chamado.tecnico_responsavel.nome_usuario
             titulo += f" por {nome_tecnico}"

        # Busca lista de técnicos para o modal de atribuição
        tecnicos = Usuario.query.join(Perfil).filter(Perfil.nome == 'Tecnico').all()
        
        # Busca grupos para o modal de agrupar demandas (excluir deletados)
        grupos = Grupo.query.filter(
            not_(Grupo.nome.like('__DEL__%'))
        ).order_by(Grupo.nome).all()

        return render_template('atendimento_demanda.html', 
                               chamado=chamado,
                               solicitante=solicitante,
                               tecnicos=tecnicos,
                               grupos=grupos,
                               historicos=historicos,
                               titulo_pagina=titulo)

    except Exception as e:
        flash(f'Erro ao abrir o chamado: {e}', 'danger')
        return redirect(url_for('tecnico.gerenciamento_demandas'))


# --- NOVA ROTA: ATENDER CHAMADO (Ação) ---
@tecnico_blue.route('/atender/<int:chamado_id>')
@login_required
def atender_chamado(chamado_id):
    try:
        chamado = Chamado.query.get_or_404(chamado_id)
        
        
        chamado.status_id = 2
        chamado.tecnico_responsavel_id = current_user.id
        
        # Registra no histórico
        novo_historico = HistoricoChamado(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            tipo_interacao="Mudanca_Status",
            detalhes=f"Chamado assumido por {current_user.nome or current_user.nome_usuario}"
        )
        
        db.session.add(novo_historico)
        db.session.commit()
        
        flash(f'Você assumiu o chamado #{chamado.id}.', 'success')
        return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atender chamado: {e}', 'danger')
        return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_id))


# --- NOVA ROTA: ATRIBUIR CHAMADO (Ação) ---
@tecnico_blue.route('/atribuir/<int:chamado_id>', methods=['POST'])
@login_required
def atribuir_chamado(chamado_id):
    try:
        chamado = Chamado.query.get_or_404(chamado_id)
        tecnico_id = request.form.get('tecnico_id')
        
        if not tecnico_id:
            flash('Selecione um técnico para atribuir.', 'warning')
            return redirect(url_for('tecnico.gerenciamento_demandas'))
            
        novo_tecnico = Usuario.query.get(tecnico_id)
        
        if not novo_tecnico:
            flash('Técnico não encontrado.', 'danger')
            return redirect(url_for('tecnico.gerenciamento_demandas'))
        
        # VALIDAÇÃO: Verificar se o técnico pertence a pelo menos um grupo em comum
        grupos_usuario_atual = set([g.id for g in current_user.grupos_tecnicos])
        grupos_novo_tecnico = set([g.id for g in novo_tecnico.grupos_tecnicos])
        
        if not grupos_usuario_atual.intersection(grupos_novo_tecnico):
            flash('Você só pode atribuir chamados para técnicos do(s) mesmo(s) grupo(s).', 'danger')
            return redirect(url_for('tecnico.gerenciamento_demandas'))
        
        # Atualiza o chamado
        chamado.tecnico_responsavel_id = tecnico_id
        chamado.status_id = 2  # Força 'Em Atendimento'
        
        # Histórico
        novo_historico = HistoricoChamado(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            tipo_interacao="Atribuicao_Tecnico",
            detalhes=f"Chamado atribuído para {novo_tecnico.nome or novo_tecnico.nome_usuario} por {current_user.nome or current_user.nome_usuario}"
        )
        
        db.session.add(novo_historico)
        db.session.commit()
        
        flash(f'Chamado atribuído com sucesso para {novo_tecnico.nome or novo_tecnico.nome_usuario}.', 'success')
        return redirect(url_for('tecnico.gerenciamento_demandas'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atribuir: {e}', 'danger')
        return redirect(url_for('tecnico.gerenciamento_demandas'))


@tecnico_blue.route('/transferir/<int:chamado_id>', methods=['POST'])
@login_required
def transferir_chamado(chamado_id):
    """
    Transfere um chamado para outro grupo.
    A demanda deixa de aparecer no gerenciamento do grupo atual.
    """
    try:
        chamado = Chamado.query.options(
            joinedload(Chamado.subcategoria).joinedload(Categoria.grupo)
        ).get_or_404(chamado_id)
        
        grupo_destino_id = request.form.get('grupo_id')
        
        if not grupo_destino_id:
            flash('Selecione um grupo de destino.', 'warning')
            return redirect(url_for('tecnico.gerenciamento_demandas'))
        
        grupo_destino = Grupo.query.get(grupo_destino_id)
        if not grupo_destino:
            flash('Grupo de destino não encontrado.', 'danger')
            return redirect(url_for('tecnico.gerenciamento_demandas'))
        
        # Busca uma categoria do grupo de destino para vincular o chamado
        categoria_destino = Categoria.query.filter_by(grupo_id=grupo_destino_id).first()
        if not categoria_destino:
            flash(f'O grupo "{grupo_destino.nome}" não possui categorias cadastradas. Não é possível transferir.', 'danger')
            return redirect(url_for('tecnico.gerenciamento_demandas'))
        
        # Guarda informação do grupo de origem
        grupo_origem = chamado.subcategoria.grupo if chamado.subcategoria else None
        grupo_origem_nome = grupo_origem.nome if grupo_origem else "Sem Grupo"
        
        # Atualiza a subcategoria do chamado para uma categoria do novo grupo
        chamado.subcategoria_id = categoria_destino.id
        
        # Remove técnico responsável (novo grupo deve atribuir)
        chamado.tecnico_responsavel_id = None
        
        # Volta status para Aberto
        chamado.status_id = 1
        
        # Registra no histórico
        novo_historico = HistoricoChamado(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            tipo_interacao="Transferencia_Grupo",
            detalhes=f"Chamado transferido de '{grupo_origem_nome}' para '{grupo_destino.nome}' por {current_user.nome or current_user.nome_usuario}"
        )
        
        db.session.add(novo_historico)
        db.session.commit()
        
        flash(f'Chamado transferido com sucesso para o grupo "{grupo_destino.nome}".', 'success')
        return redirect(url_for('tecnico.gerenciamento_demandas'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao transferir: {e}', 'danger')
        return redirect(url_for('tecnico.gerenciamento_demandas'))


# --- NOVA ROTA: CONCLUIR CHAMADO ---
@tecnico_blue.route('/concluir/<int:chamado_id>', methods=['POST'])
@login_required
def concluir_chamado(chamado_id):
    try:
        chamado = Chamado.query.get_or_404(chamado_id)
        observacao = request.form.get('observacao_conclusao', '').strip()
        
        # Verifica se o chamado tem subchamados pendentes
        # Como subchamados é lazy='dynamic', precisa chamar .all() para obter a lista
        subchamados_pendentes = [sc for sc in chamado.subchamados.all() if sc.status.nome != 'Finalizado']
        if subchamados_pendentes:
            flash(f'Atenção! Existem {len(subchamados_pendentes)} demanda(s) agrupada(s) não concluída(s). Conclua-as primeiro.', 'warning')
            return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_id))
        
        # Define status como FINALIZADO (ID 3) - NÃO aparecerá mais na lista
        chamado.status_id = 3
        chamado.data_fechamento = datetime.now()
        
        # Registra no histórico
        detalhes = f"Chamado finalizado por {current_user.nome or current_user.nome_usuario}"
        if observacao:
            detalhes += f". Observação: {observacao}"
            
        novo_historico = HistoricoChamado(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            tipo_interacao="Conclusao",
            detalhes=detalhes
        )
        
        db.session.add(novo_historico)
        db.session.commit()
        
        flash(f'Chamado #{chamado.id} foi finalizado com sucesso! Não aparecerá mais na lista de demandas ativas.', 'success')
        return redirect(url_for('tecnico.gerenciamento_demandas'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao concluir chamado: {e}', 'danger')
        return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_id))


# --- NOVA ROTA: REABRIR CHAMADO ---
@tecnico_blue.route('/reabrir/<int:chamado_id>', methods=['POST'])
@login_required
def reabrir_chamado(chamado_id):
    try:
        chamado = Chamado.query.get_or_404(chamado_id)
        motivo = request.form.get('motivo_reabertura', '').strip()
        
        if not motivo:
            flash('Informe o motivo da reabertura.', 'warning')
            return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_id))
        
        # Verifica se o chamado está finalizado (ID 3)
        if chamado.status_id != 3:
            flash('Apenas chamados finalizados podem ser reabertos.', 'warning')
            return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_id))
        
        # Define status como REABERTO (ID 5) - volta para a lista
        chamado.status_id = 5
        chamado.data_fechamento = None  # Remove data de fechamento
        chamado.tecnico_responsavel_id = current_user.id  # Atribui ao técnico que reabriu
        
        # Registra no histórico
        detalhes = f"Chamado reaberto por {current_user.nome or current_user.nome_usuario}. Motivo: {motivo}"
            
        novo_historico = HistoricoChamado(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            tipo_interacao="Reabertura",
            detalhes=detalhes
        )
        
        db.session.add(novo_historico)
        db.session.commit()
        
        flash(f'Chamado #{chamado.id} reaberto com sucesso! Agora aparece na lista com status "Reaberto".', 'success')
        return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao reabrir chamado: {e}', 'danger')
        return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_id))


# --- NOVA ROTA: AGRUPAR DEMANDA (Criar subchamado) ---
@tecnico_blue.route('/agrupar/<int:chamado_pai_id>', methods=['POST'])
@login_required
def agrupar_demanda(chamado_pai_id):
    try:
        chamado_pai = Chamado.query.get_or_404(chamado_pai_id)
        
        # Recebe dados do formulário (agora simplificados)
        titulo = request.form.get('titulo')  # Serviço (vem preenchido do chamado pai)
        descricao = request.form.get('descricao', 'Sub-demanda agrupada automaticamente')  # Descrição padrão
        subcategoria_id = request.form.get('subcategoria_id')  # Vem do chamado pai
        
        if not titulo or not subcategoria_id:
            flash('Erro: dados obrigatórios não encontrados.', 'danger')
            return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_pai_id))
        
        # Cria o subchamado já FINALIZADO (ID 3) - não aparece na lista
        novo_chamado = Chamado(
            titulo=titulo,
            descricao=descricao,
            usuario_solicitante_id=chamado_pai.usuario_solicitante_id,  # Mesmo solicitante
            subcategoria_id=subcategoria_id,  # Mesma categoria do pai
            status_id=3,  # FINALIZADO - não aparece na lista de gerenciamento
            tecnico_responsavel_id=current_user.id,  # Técnico atual
            anexo_filepath=None,  # Sem anexo
            chamado_pai_id=chamado_pai_id  # Vincula ao chamado pai
        )
        novo_chamado.data_fechamento = datetime.now()  # Define data de fechamento
        
        db.session.add(novo_chamado)
        db.session.flush()  # Para obter o ID
        
        # Registra no histórico do chamado pai
        historico_pai = HistoricoChamado(
            chamado_id=chamado_pai_id,
            usuario_id=current_user.id,
            tipo_interacao="Demanda_Agrupada",
            detalhes=f"Sub-demanda #{novo_chamado.id} criada: {titulo}"
        )
        
        # Registra no histórico do subchamado
        historico_filho = HistoricoChamado(
            chamado_id=novo_chamado.id,
            usuario_id=current_user.id,
            tipo_interacao="Criacao",
            detalhes=f"Demanda criada como sub-demanda de #{chamado_pai_id} e automaticamente concluída"
        )
        
        db.session.add(historico_pai)
        db.session.add(historico_filho)
        db.session.commit()
        
        flash(f'Sub-demanda #{novo_chamado.id} criada e vinculada com sucesso!', 'success')
        return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_pai_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao agrupar demanda: {e}', 'danger')
        return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_pai_id))


# --- ROTA: SUSPENDER CHAMADO TEMPORARIAMENTE (Status ID 3) ---
@tecnico_blue.route('/suspender/<int:chamado_id>', methods=['POST'])
@login_required
def suspender_chamado(chamado_id):
    try:
        chamado = Chamado.query.get_or_404(chamado_id)
        motivo = request.form.get('motivo')
        
        if not motivo or motivo.strip() == '':
            flash('Informe o motivo da suspensão.', 'warning')
            return redirect(url_for('tecnico.gerenciamento_demandas'))
        
        # Atualiza para status SUSPENSA (ID 6) - CONTINUA aparecendo na lista com badge cinza
        chamado.status_id = 6
        
        # Registra no histórico
        novo_historico = HistoricoChamado(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            tipo_interacao="Suspensao",
            detalhes=f"Chamado suspenso temporariamente por {current_user.nome or current_user.nome_usuario}. Motivo: {motivo}"
        )
        
        db.session.add(novo_historico)
        db.session.commit()
        
        flash(f'Chamado #{chamado.id} foi suspenso temporariamente e permanece na lista com status "Suspensa".', 'warning')
        return redirect(url_for('tecnico.gerenciamento_demandas'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao suspender chamado: {e}', 'danger')
        return redirect(url_for('tecnico.gerenciamento_demandas'))

# --- ROTA: CANCELAR CHAMADO DEFINITIVAMENTE (Status ID 4) ---
@tecnico_blue.route('/cancelar/<int:chamado_id>', methods=['POST'])
@login_required
def cancelar_chamado(chamado_id):
    try:
        chamado = Chamado.query.get_or_404(chamado_id)
        motivo = request.form.get('motivo')
        
        if not motivo or motivo.strip() == '':
            flash('Informe o motivo do cancelamento definitivo.', 'warning')
            return redirect(url_for('tecnico.gerenciamento_demandas'))
        
        # Atualiza para status "Cancelado" (ID 4) - NÃO aparecerá mais na lista
        chamado.status_id = 4
        
        # Registra no histórico
        novo_historico = HistoricoChamado(
            chamado_id=chamado.id,
            usuario_id=current_user.id,
            tipo_interacao="Mudanca_Status",
            detalhes=f"Chamado cancelado definitivamente por {current_user.nome or current_user.nome_usuario}. Motivo: {motivo}"
        )
        
        db.session.add(novo_historico)
        db.session.commit()
        
        flash(f'Chamado #{chamado.id} foi cancelado definitivamente.', 'success')
        return redirect(url_for('tecnico.gerenciamento_demandas'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cancelar chamado: {e}', 'danger')
        return redirect(url_for('tecnico.gerenciamento_demandas'))

# Rota auxiliar para visualizar (redireciona para atendimento)
@tecnico_blue.route('/visualizar/<int:chamado_id>')
@login_required
def visualizar_demanda(chamado_id):
    return redirect(url_for('tecnico.atendimento_chamado', chamado_id=chamado_id))

# --- API: BUSCAR CATEGORIAS (Grupos de Serviço) POR GRUPO ---
@tecnico_blue.route('/api/categorias-por-grupo/<int:grupo_id>', methods=['GET'])
@login_required
def buscar_categorias_por_grupo(grupo_id):
    try:
        # CORREÇÃO: Filtra deletadas com __DEL__
        categorias = Categoria.query.filter(
            Categoria.grupo_id == grupo_id,
            not_(Categoria.nome.startswith('__DEL__'))
        ).order_by(Categoria.nome).all()
        
        lista_categorias = []
        for cat in categorias:
            lista_categorias.append({
                'id': cat.id,
                'nome': cat.nome
            })
        
        return jsonify(lista_categorias)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- API: BUSCAR ITENS (Serviços) POR CATEGORIA ---
@tecnico_blue.route('/api/itens-por-categoria/<int:categoria_id>', methods=['GET'])
@login_required
def buscar_itens_por_categoria(categoria_id):
    try:
        # CORREÇÃO: Filtra deletados com __DEL__
        itens = Item.query.filter(
            Item.categoria_id == categoria_id,
            not_(Item.nome.startswith('__DEL__'))
        ).order_by(Item.nome).all()
        
        lista_itens = []
        for item in itens:
            lista_itens.append({
                'id': item.id,
                'nome': item.nome
            })
        
        return jsonify(lista_itens)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@tecnico_blue.route('/api/comentarios/<int:chamado_id>', methods=['GET'])
@login_required
def listar_comentarios(chamado_id):
    try:
        comentarios = Comentario.query.filter_by(chamado_id=chamado_id).order_by(Comentario.data_envio.asc()).all()
        
        lista_json = []
        for c in comentarios:
            is_me = (c.usuario_id == current_user.id)
            
            # Formata dados do anexo se existir
            anexo_info = None
            if c.anexo_filepath:
                nome_arquivo = c.anexo_filepath.split('_', 1)[-1] # Remove o timestamp do nome
                url_arquivo = url_for('static', filename='uploads/' + c.anexo_filepath)
                anexo_info = {'nome': nome_arquivo, 'url': url_arquivo}

            lista_json.append({
                'id': c.id,
                'texto': c.texto,
                'usuario_nome': c.usuario.nome or c.usuario.nome_usuario,
                'data': c.data_envio.strftime('%d/%m %H:%M'),
                'is_me': is_me,
                'anexo': anexo_info # Envia para o front
            })
            
        return jsonify(lista_json)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
def arquivo_permitido(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@tecnico_blue.route('/api/comentarios/<int:chamado_id>/enviar', methods=['POST'])
@login_required
def enviar_comentario(chamado_id):
    """
    API para salvar um novo comentário com segurança de arquivo.
    """
    try:
        # Verifica se é JSON ou Form Data
        texto = ""
        arquivo = None
        
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
            texto = data.get('texto')
        else:
            texto = request.form.get('texto', '')
            arquivo = request.files.get('arquivo')

        if not texto and not arquivo:
            return jsonify({'error': 'Mensagem vazia'}), 400

        # Processamento do Arquivo com SEGURANÇA
        anexo_path = None
        if arquivo and arquivo.filename != '':
            from werkzeug.utils import secure_filename
            import os
            import uuid
            
            # Validação de Extensão (Bloqueia .exe, .bat, etc)
            if not arquivo_permitido(arquivo.filename):
                return jsonify({'error': 'Tipo de arquivo não permitido por segurança.'}), 415
            
            # Salva o arquivo
            original_filename = secure_filename(arquivo.filename)
            unique_filename = f"{uuid.uuid4()}_{original_filename}"
            
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            arquivo.save(os.path.join(upload_folder, unique_filename))
            anexo_path = unique_filename
            
            if not texto:
                texto = f"Enviou um anexo: {original_filename}"

        novo_comentario = Comentario(
            chamado_id=chamado_id,
            usuario_id=current_user.id,
            texto=texto,
            anexo_filepath=anexo_path
        )
        
        db.session.add(novo_comentario)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@tecnico_blue.route('/api/demandas/atualizacao', methods=['GET'])
@login_required
def api_atualizacao_demandas():
    try:
        grupo_id = request.args.get('grupo_id', type=int)
        if not grupo_id:
            return jsonify([])

        # Query otimizada com joins
        query = Chamado.query.options(
            joinedload(Chamado.status),
            joinedload(Chamado.solicitante),
            joinedload(Chamado.subcategoria).joinedload(Categoria.grupo),
            joinedload(Chamado.tecnico_responsavel)
        ).join(Categoria).join(Grupo).filter(
            Chamado.status_id.in_([1, 2, 5, 6]),
            Categoria.grupo_id == grupo_id,
            not_(Grupo.nome.startswith('__DEL__')),
            not_(Categoria.nome.startswith('__DEL__'))
        )
        
        demandas = query.order_by(Chamado.data_abertura.desc()).all()
        
        resultado = []
        for d in demandas:
            # Status e Classe CSS
            status_class = 'badge-secondary'
            if d.status.id == 1: status_class = 'badge-danger'      # Aberto
            elif d.status.id == 2: status_class = 'badge-warning'   # Em Andamento
            elif d.status.id == 5: status_class = 'badge-info'      # Reaberto
            elif d.status.id == 6: status_class = 'badge-secondary' # Suspensa

            # Descrição Limpa
            desc_limpa = d.get_descricao_limpa()
            desc_curta = (desc_limpa[:50] + '...') if len(desc_limpa) > 50 else desc_limpa

            # --- CORREÇÃO AQUI: Nome do Técnico ---
            tecnico_nome = "Não atribuído"
            tecnico_id = None
            
            if d.tecnico_responsavel:
                # Prioriza o Nome, senão usa o login (nome_usuario)
                tecnico_nome = d.tecnico_responsavel.nome or d.tecnico_responsavel.nome_usuario
                tecnico_id = d.tecnico_responsavel.id
            
            resultado.append({
                'id': d.id,
                'ano': d.data_abertura.year,
                'data_formatada': d.data_abertura.strftime('%d/%m/%Y %H:%M'),
                'solicitante': d.solicitante.nome or d.solicitante.nome_usuario,
                'unidade': d.solicitante.unidade_lotacao or '',
                'descricao_curta': desc_curta or 'Sem descrição',
                'descricao_full': desc_limpa,
                'servico': d.titulo,
                'resumo_servico': d.subcategoria.nome,
                'status': d.status.nome,
                'status_class': status_class,
                'tecnico': tecnico_nome,        # Nome para exibir
                'tecnico_id': tecnico_id,       # ID para lógica do botão
                'meu_id': current_user.id,      # ID do usuário logado
                'url_visualizar': url_for('tecnico.atendimento_chamado', chamado_id=d.id),
                'url_atender': url_for('tecnico.atender_chamado', chamado_id=d.id)
            })
            
        return jsonify(resultado)
    except Exception as e:
        print(f"ERRO API: {e}") # Debug no terminal
        return jsonify({'error': str(e)}), 500