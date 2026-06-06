from flask import render_template, url_for, request, redirect, session, Blueprint, flash, jsonify
from flask_login import login_required, current_user
from servicos.model import * 
from servicos.functions import *
from servicos import app, db
from sqlalchemy import not_

# Imports para Upload
import os
import uuid
from werkzeug.utils import secure_filename
import sys
# Import para consultas avançadas (otimização)
from sqlalchemy.orm import joinedload


padrao_blue = Blueprint('padrao', __name__, template_folder='templates')

@padrao_blue.route('/dashboard')
@login_required
def rendDashboardPadrao(): 
    try:
        from servicos.model import Grupo # Importação interna
        
        grupos = Grupo.query.filter(not_(Grupo.nome.like('__DEL__%'))).order_by(Grupo.nome).all()
        
        # AJUSTE AQUI:
        if current_user.perfil.nome == 'Administrador':
            grupos_usuario = grupos
        else:
            # Se for padrão, ele pode não ter grupos_tecnicos. 
            # Usamos getattr para evitar erro caso o atributo não exista
            grupos_usuario = getattr(current_user, 'grupos_tecnicos', [])
        
        return render_template('dashboard_padrao.html', 
                               grupos=grupos, 
                               grupos_usuario=grupos_usuario, 
                               titulo_pagina="Registrar Demanda")
    except Exception as e:
        # Se der erro, mostre o erro real no console para você identificar
        print(f"Erro no Dashboard: {e}")
        return f"Erro ao carregar dashboard: {e}"

@padrao_blue.route('/api/notificacoes')
@login_required
def api_notificacoes():
    """
    API para retornar notificações personalizadas por perfil do usuário
    """
    try:
        from datetime import datetime, timedelta
        lista_notificacoes = []
        periodo_dias = 7
        data_limite = datetime.now() - timedelta(days=periodo_dias)
        
        ultima_atualizacao_str = request.args.get('ultima_atualizacao')
        apenas_novas = False
        
        if ultima_atualizacao_str:
            try:
                ultima_atualizacao = datetime.fromisoformat(ultima_atualizacao_str)
                if ultima_atualizacao > data_limite:
                    data_limite = ultima_atualizacao
                    apenas_novas = True
            except ValueError:
                pass  
        
        perfil_usuario = current_user.perfil.nome if current_user.perfil else 'Padrao'
        
        # =========================================================
        # BLOCO 1: TÉCNICOS E ADMINISTRADORES
        # =========================================================
        if perfil_usuario in ['Tecnico', 'Tecnico_adm', 'Administrador']:
            
            atribuicoes = HistoricoChamado.query.options(
                joinedload(HistoricoChamado.chamado),
                joinedload(HistoricoChamado.usuario)
            ).join(Chamado).filter(
                HistoricoChamado.tipo_interacao == 'Atribuicao_Tecnico',
                HistoricoChamado.data_interacao >= data_limite,
                Chamado.tecnico_responsavel_id == current_user.id
            ).order_by(HistoricoChamado.data_interacao.desc()).limit(5).all()
            
            for reg in atribuicoes:
                ticket = reg.chamado
                # Proteção caso o usuário venha nulo (ações do sistema)
                nome_autor = reg.usuario.nome if reg.usuario and reg.usuario.nome else 'Sistema'
                
                lista_notificacoes.append({
                    'id': f"atrib_{reg.id}",
                    'tipo': 'atribuicao',
                    'titulo': f'O ticket {ticket.id}-{ticket.data_abertura.year} foi encaminhado para você!',
                    'descricao': f'Por {nome_autor}',
                    'data': reg.data_interacao.strftime('%d/%m/%Y %H:%M'),
                    'chamado_id': ticket.id,
                    'lida': False
                })
            
            mudancas = HistoricoChamado.query.options(
                joinedload(HistoricoChamado.chamado),
                joinedload(HistoricoChamado.usuario)
            ).join(Chamado).filter(
                HistoricoChamado.tipo_interacao == 'Mudanca_Status',
                HistoricoChamado.data_interacao >= data_limite,
                Chamado.tecnico_responsavel_id == current_user.id,
                HistoricoChamado.usuario_id != current_user.id
            ).order_by(HistoricoChamado.data_interacao.desc()).limit(3).all()
            
            for reg in mudancas:
                ticket = reg.chamado
                msg_titulo = f'Ticket {ticket.id}-{ticket.data_abertura.year} atualizado'
                if 'assumido' in reg.detalhes.lower():
                    msg_titulo = f'Ticket {ticket.id}-{ticket.data_abertura.year} foi assumido'
                elif 'cancelado' in reg.detalhes.lower() or 'suspens' in reg.detalhes.lower():
                    msg_titulo = f'Ticket {ticket.id}-{ticket.data_abertura.year} foi cancelado'
                    
                nome_autor = reg.usuario.nome if reg.usuario and reg.usuario.nome else 'Sistema'
                    
                lista_notificacoes.append({
                    'id': f"status_{reg.id}",
                    'tipo': 'status_change',
                    'titulo': msg_titulo,
                    'descricao': f'Por {nome_autor}',
                    'data': reg.data_interacao.strftime('%d/%m/%Y %H:%M'),
                    'chamado_id': ticket.id,
                    'lida': False
                })
        
        # =========================================================
        # BLOCO 2: USUÁRIOS PADRÃO (Onde estava o problema)
        # =========================================================
        else:
            # 1. Pegamos a lista exata de IDs do banco e convertemos para uma lista Python simples
            meus_chamados = db.session.query(Chamado.id).filter_by(
                usuario_solicitante_id=current_user.id
            ).all()
            
            meus_tickets_ids = [c[0] for c in meus_chamados] # Resultado: [1, 2, 5, 8...]
            
            # 2. Só fazemos a busca no histórico se a lista de tickets não estiver vazia
            if meus_tickets_ids:
                atualizacoes = HistoricoChamado.query.options(
                    joinedload(HistoricoChamado.chamado),
                    joinedload(HistoricoChamado.usuario)
                ).filter(
                    HistoricoChamado.chamado_id.in_(meus_tickets_ids), # Agora o in_() funciona perfeitamente
                    HistoricoChamado.data_interacao >= data_limite,
                    HistoricoChamado.usuario_id != current_user.id
                ).order_by(HistoricoChamado.data_interacao.desc()).limit(8).all()
                
                for reg in atualizacoes:
                    ticket = reg.chamado
                    tipo_notif = 'atribuicao' if reg.tipo_interacao == 'Atribuicao_Tecnico' else 'status_change'
                    
                    lista_notificacoes.append({
                        'id': f"upd_{reg.id}",
                        'tipo': tipo_notif,
                        'titulo': f'Seu ticket {ticket.id}-{ticket.data_abertura.year} foi atualizado',
                        'descricao': reg.detalhes[:80] if reg.detalhes else 'Atualização realizada',
                        'data': reg.data_interacao.strftime('%d/%m/%Y %H:%M'),
                        'chamado_id': ticket.id,
                        'lida': False
                    })
        
        # Ordenar e retornar
        lista_notificacoes.sort(key=lambda x: datetime.strptime(x['data'], '%d/%m/%Y %H:%M'), reverse=True)
        quantidade_total = len(lista_notificacoes[:10])
        timestamp_atual = datetime.now().isoformat()
        
        return jsonify({
            'notificacoes': lista_notificacoes[:10],
            'total': quantidade_total,
            'timestamp': timestamp_atual,
            'apenas_novas': apenas_novas
        })
        
    except Exception as erro:
        print(f"Erro na API de notificações: {erro}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'notificacoes': [],
            'total': 0,
            'erro': str(erro)
        }), 500

@padrao_blue.route('/api/notificacoes/marcar-lida/<notif_id>', methods=['POST'])
@login_required
def marcar_notificacao_lida(notif_id):
    """
    Marca uma notificação como lida (implementação futura)
    """
    try:
        # Por enquanto apenas simula que foi marcada
        return jsonify({'success': True, 'message': 'Notificação marcada como lida'})
    except Exception as e:
        return jsonify({'success': False, 'erro': str(e)}), 500

@padrao_blue.route('/grupo/<int:grupo_id>')
@login_required
def mostrar_subcategorias(grupo_id):
    try:
        grupo = Grupo.query.get_or_404(grupo_id)
        
        # CORREÇÃO: Verifica se o próprio grupo não está deletado
        if grupo.nome.startswith('__DEL__'):
            flash('Este grupo de serviços não está mais disponível.', 'warning')
            return redirect(url_for('padrao.rendDashboardPadrao'))

        # CORREÇÃO: Filtra apenas categorias NÃO deletadas
        categorias = Categoria.query.filter(
            Categoria.grupo_id == grupo.id,
            not_(Categoria.nome.startswith('__DEL__'))
        ).all()
        
        # Obter grupos do usuário (para exibir no dropdown)
        if current_user.perfil.nome == 'Administrador':
            grupos_usuario = Grupo.query.filter(
                not_(Grupo.nome.like('__DEL__%'))
            ).order_by(Grupo.nome).all()
        else:
            grupos_usuario = getattr(current_user, 'grupos_tecnicos', [])
        
        return render_template('subcategorias.html', 
                               grupo=grupo, 
                               categorias=categorias,
                               grupos_usuario=grupos_usuario,
                               titulo_pagina=f"Serviços de {grupo.nome}")
    except Exception as e:
        flash(f'Ocorreu um erro ao carregar as subcategorias: {e}', 'danger')
        return redirect(url_for('padrao.rendDashboardPadrao'))

@padrao_blue.route('/categoria/<int:categoria_id>')
@login_required
def mostrar_itens(categoria_id):
    try:
        categoria = Categoria.query.get_or_404(categoria_id)
        
        # CORREÇÃO: Verifica se a categoria foi deletada
        if categoria.nome.startswith('__DEL__'):
            flash('Esta categoria não está mais disponível.', 'warning')
            return redirect(url_for('padrao.rendDashboardPadrao'))
            
        grupo = categoria.grupo 
        
        # CORREÇÃO: Filtra apenas itens NÃO deletados
        itens = Item.query.filter(
            Item.categoria_id == categoria.id,
            not_(Item.nome.startswith('__DEL__'))
        ).all()
        
        # Obter grupos do usuário (para exibir no dropdown)
        if current_user.perfil.nome == 'Administrador':
            grupos_usuario = Grupo.query.filter(
                not_(Grupo.nome.like('__DEL__%'))
            ).order_by(Grupo.nome).all()
        else:
            grupos_usuario = getattr(current_user, 'grupos_tecnicos', [])
        
        return render_template('itens.html', 
                               grupo=grupo, 
                               categoria=categoria, 
                               itens=itens,
                               grupos_usuario=grupos_usuario,
                               titulo_pagina=f"Itens de {categoria.nome}")
    except Exception as e:
        flash(f'Ocorreu um erro ao carregar os itens: {e}', 'danger')
        return redirect(url_for('padrao.rendDashboardPadrao'))

@padrao_blue.route('/registrar/<int:item_id>', methods=['GET', 'POST'])
@login_required
def registrar_demanda(item_id):
    try:
        # Importe os modelos necessários
        from servicos.model import Formulario, Item, Chamado, Categoria, Grupo
        
        item = Item.query.get_or_404(item_id)
        
        # Bloqueio de itens deletados
        if item.nome.startswith('__DEL__'):
            flash('Este serviço foi descontinuado.', 'danger')
            return redirect(url_for('padrao.rendDashboardPadrao'))
            
        categoria = item.categoria
        grupo = categoria.grupo
        
        # BUSCA SE EXISTE UM FORMULÁRIO ATIVO VINCULADO A ESSE ITEM
        formulario_personalizado = Formulario.query.filter_by(item_id=item.id, ativo=True).first()
        
    except Exception as e:
        flash(f'Erro ao carregar serviço: {e}', 'danger')
        return redirect(url_for('padrao.rendDashboardPadrao'))

    if request.method == 'POST':
        try:
            # Dados padrão
            email = request.form.get('email')
            ramal = request.form.get('ramal')
            # Detalhamento base (pode vir vazio se o form for personalizado)
            detalhamento_base = request.form.get('detalhamento', '')
            
            # --- LÓGICA DO FORMULÁRIO PERSONALIZADO ---
            texto_formulario = ""
            
            if formulario_personalizado:
                texto_formulario += f"\n--- DADOS DO FORMULÁRIO: {formulario_personalizado.titulo} ---\n"
                
                # Itera sobre os campos esperados para pegar as respostas
                # Ordenamos para garantir que apareça na ordem certa
                campos_ordenados = sorted(formulario_personalizado.campos, key=lambda x: x.ordem)
                
                for campo in campos_ordenados:
                    # O nome do input no HTML será "campo_ID"
                    resposta = request.form.get(f'campo_{campo.id}')
                    
                    # Validação de obrigatório (Back-end)
                    if campo.obrigatorio and not resposta:
                        flash(f'O campo "{campo.label}" é obrigatório.', 'warning')
                        return render_template('formulario_demanda.html', grupo=grupo, categoria=categoria, item=item, formulario=formulario_personalizado, titulo_pagina=f"Registrar: {item.nome}")
                    
                    # Formata a resposta para salvar na descrição
                    if resposta:
                        texto_formulario += f"{campo.label}: {resposta}\n"
                    else:
                        texto_formulario += f"{campo.label}: (Não informado)\n"
                
                texto_formulario += "------------------------------------------\n"

            # Junta tudo na descrição final
            descricao_final = detalhamento_base
            if texto_formulario:
                # Se tiver formulário, junta o texto do form + observação extra
                descricao_final = texto_formulario + "\nObs Adicional:\n" + detalhamento_base

            # Upload de arquivo (Lógica mantida)
            anexo_path_para_salvar = None
            if 'arquivo' in request.files:
                file = request.files['arquivo']
                if file and file.filename != '':
                    original_filename = secure_filename(file.filename)
                    unique_filename = str(uuid.uuid4()) + "_" + original_filename
                    if not app.config.get('UPLOAD_FOLDER'): raise Exception("Config UPLOAD_FOLDER ausente")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                    anexo_path_para_salvar = unique_filename
            
            # Atualiza dados do usuário
            if current_user.email != email: current_user.email = email
            if current_user.telefone != ramal: current_user.telefone = ramal
            
            # Cria o chamado
            novo_chamado = Chamado(
                titulo=item.nome,
                descricao=descricao_final, # Descrição contém os dados do form formatados
                usuario_solicitante_id=current_user.id,
                subcategoria_id=item.categoria_id, 
                status_id=1, 
                anexo_filepath=anexo_path_para_salvar
            )
            
            db.session.add(current_user)
            db.session.add(novo_chamado)
            db.session.commit()
            
            # (Seu código de envio de e-mail assíncrono continua aqui...)
            
            flash('Demanda registrada com sucesso!', 'success')
            return redirect(url_for('padrao.rendDashboardPadrao'))

        except Exception as e:
            db.session.rollback() 
            flash(f'Erro ao registrar: {str(e)}', 'danger')
            
    # GET: Renderiza o template passando o formulário (se existir)
    return render_template('formulario_demanda.html',
                           grupo=grupo,
                           categoria=categoria,
                           item=item,
                           formulario=formulario_personalizado, # Passamos o objeto aqui
                           titulo_pagina=f"Registrar: {item.nome}")


@padrao_blue.route('/minhas_demandas')
@login_required
def minhas_demandas():
    try:
        from datetime import datetime
        
        # Parâmetros de filtro
        ticket = request.args.get('ticket', '').strip()
        status_id = request.args.get('status', '').strip()
        servico = request.args.get('servico', '').strip()
        data_filtro = request.args.get('data', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Itens por página
        
        # Query base - apenas demandas do usuário atual
        query = Chamado.query.options(
            joinedload(Chamado.status),
            joinedload(Chamado.subcategoria).joinedload(Categoria.grupo),
            joinedload(Chamado.tecnico_responsavel)
        ).join(
            Categoria, Chamado.subcategoria_id == Categoria.id
        ).join(
            Grupo, Categoria.grupo_id == Grupo.id
        ).filter(
            Chamado.usuario_solicitante_id == current_user.id,
            # FILTRO DE DELETE LÓGICO:
            not_(Grupo.nome.startswith('__DEL__')),
            not_(Categoria.nome.startswith('__DEL__'))
        )
        
        # Aplicar filtros
        if ticket:
            # Busca por ticket (ex: 123-2025)
            try:
                ticket_parts = ticket.split('-')
                if len(ticket_parts) == 2:
                    ticket_id = int(ticket_parts[0])
                    query = query.filter(Chamado.id == ticket_id)
                else:
                    query = query.filter(Chamado.id == int(ticket))
            except:
                pass
        
        if status_id:
            query = query.filter(Chamado.status_id == int(status_id))
        
        if servico:
            # Busca por nome do serviço
            query = query.join(Chamado.subcategoria).filter(
                Item.nome.ilike(f'%{servico}%')
            )
        
        if data_filtro:
            # Filtra por data específica
            try:
                data_obj = datetime.strptime(data_filtro, '%Y-%m-%d').date()
                query = query.filter(db.func.date(Chamado.data_abertura) == data_obj)
            except:
                pass
        
        # Ordenar por data (mais recentes primeiro)
        query = query.order_by(Chamado.data_abertura.desc())
        
        # Paginação
        total = query.count()
        demandas_paginadas = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Calcular informações de paginação
        total_pages = (total + per_page - 1) // per_page
        start_item = (page - 1) * per_page + 1
        end_item = min(page * per_page, total)
        
        # Calcular páginas visíveis (máximo 7 páginas)
        max_pages_shown = 7
        if total_pages <= max_pages_shown:
            start_page = 1
            end_page = total_pages
        else:
            if page <= max_pages_shown // 2:
                start_page = 1
                end_page = max_pages_shown
            elif page >= total_pages - max_pages_shown // 2:
                start_page = total_pages - max_pages_shown + 1
                end_page = total_pages
            else:
                start_page = page - max_pages_shown // 2
                end_page = page + max_pages_shown // 2
        
        pagination = {
            'page': page,
            'pages': total_pages,
            'total': total,
            'start': start_item if total > 0 else 0,
            'end': end_item,
            'start_page': start_page,
            'end_page': end_page
        }

        # Obter grupos do usuário (para exibir no dropdown)
        if current_user.perfil.nome == 'Administrador':
            grupos_usuario = Grupo.query.filter(not_(Grupo.nome.like('__DEL__%'))).order_by(Grupo.nome).all()
        else:
            # Mesmo ajuste de segurança aqui
            grupos_usuario = getattr(current_user, 'grupos_tecnicos', [])

        return render_template('minhas_demandas.html', 
                               demandas=demandas_paginadas.items, 
                               pagination=pagination,
                               grupos_usuario=grupos_usuario,
                               titulo_pagina="Minhas Demandas")
    except Exception as e:
        flash(f'Ocorreu um erro ao carregar suas demandas: {e}', 'danger')
        return redirect(url_for('padrao.rendDashboardPadrao'))
    
@padrao_blue.route('/minhas_demandas/<int:chamado_id>')
@login_required
def visualizar_minha_demanda(chamado_id):
    """
    Tela de detalhes da demanda para o usuário solicitante.
    Mostra status, histórico e chat.
    """
    try:
        # Busca o chamado com as relações
        chamado = Chamado.query.options(
            joinedload(Chamado.status),
            joinedload(Chamado.tecnico_responsavel),
            joinedload(Chamado.subcategoria).joinedload(Categoria.grupo)
        ).get_or_404(chamado_id)
        
        # SEGURANÇA: Verifica se o chamado pertence ao usuário logado
        if chamado.usuario_solicitante_id != current_user.id:
            flash('Você não tem permissão para visualizar esta demanda.', 'danger')
            return redirect(url_for('padrao.minhas_demandas'))

        # Buscar histórico do chamado
        historicos = HistoricoChamado.query.options(
            joinedload(HistoricoChamado.usuario)
        ).filter_by(chamado_id=chamado_id).order_by(HistoricoChamado.data_interacao.desc()).all()

        titulo = f"Ticket Nº: {chamado.id}-{chamado.data_abertura.year} - {chamado.status.nome}"
        
        # Obter grupos do usuário (para exibir no dropdown)
        if current_user.perfil.nome == 'Administrador':
            grupos_usuario = Grupo.query.filter(
                not_(Grupo.nome.like('__DEL__%'))
            ).order_by(Grupo.nome).all()
        else:
            grupos_usuario = getattr(current_user, 'grupos_tecnicos', [])
        
        # Renderiza o novo template que criamos
        return render_template('visualizar_demanda_usuario.html', 
                               chamado=chamado,
                               historicos=historicos,
                               grupos_usuario=grupos_usuario,
                               titulo_pagina=titulo)

    except Exception as e:
        flash(f'Erro ao abrir a demanda: {e}', 'danger')
        return redirect(url_for('padrao.minhas_demandas'))


# --- *** API DE BUSCA CORRIGIDA *** ---
@padrao_blue.route('/api/search')
@login_required
def api_search():
    query_str = request.args.get('q', '')
    
    if len(query_str) < 2:
        return jsonify([]) 

    search_term = f"%{query_str}%"
    PREFIXO_DEL = "__DEL__"
    
    resultados = db.session.query(Item, Categoria, Grupo).join(
        Categoria, Item.categoria_id == Categoria.id
    ).join(
        Grupo, Categoria.grupo_id == Grupo.id
    ).filter(
        # 1. BLOQUEIO: Garante que nada deletado apareça na busca
        not_(Grupo.nome.startswith(PREFIXO_DEL)),
        not_(Categoria.nome.startswith(PREFIXO_DEL)),
        not_(Item.nome.startswith(PREFIXO_DEL)),
        
        # 2. BUSCA: Procura o termo nos campos
        db.or_(
            Item.nome.ilike(search_term),
            Item.descricao.ilike(search_term),
            Categoria.nome.ilike(search_term),
            Categoria.descricao.ilike(search_term),
            Grupo.nome.ilike(search_term),
            Grupo.descricao.ilike(search_term)
        )
    ).limit(10).all()
    
    lista_json = []
    for item, categoria, grupo in resultados:
        lista_json.append({
            'id': item.id,
            'nome': item.nome,
            'categoria': categoria.nome,
            'grupo': grupo.nome
        })
    
    return jsonify(lista_json)

@padrao_blue.route('/avaliar_demanda', methods=['POST'])
@login_required
def avaliar_demanda():
    try:
        # 1. Captura os dados do formulário PRIMEIRO
        chamado_id = request.form.get('chamado_id')
        nota = int(request.form.get('avaliacao'))
        motivo_reabertura = request.form.get('motivo_reabertura')
        quer_reabrir = request.form.get('reabrir_check') == 'on'
        
        # 2. Busca o chamado no banco
        chamado = Chamado.query.get_or_404(chamado_id)
        
        # Segurança: verificar se o usuário é o dono do chamado
        if chamado.usuario_solicitante_id != current_user.id:
            flash('Permissão negada.', 'danger')
            return redirect(url_for('padrao.minhas_demandas'))

        # 3. Salva a avaliação (independente de reabrir ou não)
        chamado.avaliacao = nota
        
        # 4. Lógica de Reabertura (Se nota baixa E checkbox marcado)
        if nota <= 2 and quer_reabrir:
            chamado.comentario_avaliacao = motivo_reabertura
            chamado.status_id = 5  # Status: Reaberto
            chamado.tecnico_responsavel_id = None # Opcional: Remove o técnico para voltar à fila geral
            
            # Registra no histórico
            novo_historico = HistoricoChamado(
                chamado_id=chamado.id,
                usuario_id=current_user.id,
                tipo_interacao='Reabertura',
                detalhes=f"Reaberto pelo usuário após avaliação negativa ({nota} estrelas). Motivo: {motivo_reabertura}"
            )
            db.session.add(novo_historico)
            flash('Sua avaliação foi registrada e o chamado foi REABERTO para análise.', 'warning')
            
        else:
            # Caso contrário, apenas salva a nota e agradece
            # Se quiser salvar o comentário mesmo sem reabrir, descomente a linha abaixo:
            # chamado.comentario_avaliacao = motivo_reabertura 
            flash('Obrigado pela sua avaliação!', 'success')

        db.session.commit()
        return redirect(url_for('padrao.minhas_demandas'))

    except Exception as e:
        db.session.rollback()
        # O erro apareceu aqui porque 'e' capturou o NameError
        flash(f'Erro ao avaliar: {str(e)}', 'danger')
        return redirect(url_for('padrao.minhas_demandas'))

@padrao_blue.route('/emprestimos')
@padrao_blue.route('/emprestimos/<int:grupo_id>')
@login_required
def emprestimos(grupo_id=None):
    """
    Página de gerenciamento de empréstimos
    """
    try:
        # Obter grupos do usuário (para exibir no dropdown do header)
        if current_user.perfil.nome == 'Administrador':
            grupos_usuario = Grupo.query.filter(
                not_(Grupo.nome.like('__DEL__%')),
                Grupo.emprestimo_ativo == True
            ).order_by(Grupo.nome).all()
        else:
            # Apenas grupos com empréstimo ativo
            grupos_usuario = [g for g in getattr(current_user, 'grupos_tecnicos', []) if g.emprestimo_ativo]
        
        # Se não tem grupo_id, pegar o primeiro grupo disponível
        if not grupo_id and grupos_usuario:
            grupo_id = grupos_usuario[0].id
        
        # Verificar permissão do grupo
        if grupo_id:
            grupo_atual = Grupo.query.get_or_404(grupo_id)
            if current_user.perfil.nome != 'Administrador':
                if grupo_atual not in getattr(current_user, 'grupos_tecnicos', []):
                    flash('Você não tem permissão para acessar este grupo.', 'danger')
                    return redirect(url_for('padrao.rendDashboardPadrao'))
        else:
            flash('Nenhum grupo com empréstimos habilitado.', 'warning')
            return redirect(url_for('padrao.rendDashboardPadrao'))
        
        # Buscar empréstimos do grupo
        emprestimos_lista = Emprestimo.query.filter(
            Emprestimo.grupo_id == grupo_id
        ).order_by(Emprestimo.data_emprestimo.desc()).all()
        
        # Buscar todos os usuários para o select
        usuarios = Usuario.query.filter(
            Usuario.ativo == True,
            not_(Usuario.nome.like('__DEL__%'))
        ).order_by(Usuario.nome).all()
        
        # Calcular estatísticas
        total_emprestimos = len(emprestimos_lista)
        emprestimos_ativos = sum(1 for emp in emprestimos_lista if emp.status == 'Ativo')
        emprestimos_atrasados = sum(1 for emp in emprestimos_lista if emp.status == 'Atrasado')
        emprestimos_devolvidos = sum(1 for emp in emprestimos_lista if emp.status == 'Devolvido')
        
        return render_template('emprestimos.html', 
                             grupos_usuario=grupos_usuario,
                             grupo_atual=grupo_atual,
                             titulo_pagina="Empréstimos",
                             emprestimos=emprestimos_lista,
                             usuarios=usuarios,
                             total_emprestimos=total_emprestimos,
                             emprestimos_ativos=emprestimos_ativos,
                             emprestimos_atrasados=emprestimos_atrasados,
                             emprestimos_devolvidos=emprestimos_devolvidos)
    except Exception as e:
        flash(f'Erro ao carregar página de empréstimos: {str(e)}', 'danger')
        return redirect(url_for('padrao.rendDashboardPadrao'))


@padrao_blue.route('/emprestimos/novo', methods=['POST'])
@login_required
def novo_emprestimo():
    """
    Criar novo empréstimo
    """
    try:
        # Obter dados do formulário
        usuario_id = request.form.get('usuario_id')
        solicitante_nome = request.form.get('solicitante_nome')
        solicitante_matricula = request.form.get('solicitante_matricula')
        solicitante_cargo = request.form.get('solicitante_cargo')
        solicitante_unidade = request.form.get('solicitante_unidade')
        solicitante_ramal = request.form.get('solicitante_ramal')
        data_emprestimo_str = request.form.get('data_emprestimo')
        data_previsao_str = request.form.get('data_previsao')
        observacao = request.form.get('observacao')
        
        # Obter arrays de equipamentos e patrimônios
        equipamentos = request.form.getlist('equipamentos[]')
        patrimonios = request.form.getlist('patrimonios[]')
        
        # Validações
        if not data_emprestimo_str or not data_previsao_str:
            flash('Preencha todos os campos obrigatórios!', 'warning')
            return redirect(url_for('padrao.emprestimos'))
        
        # Validar se tem usuário ou dados manuais
        if not usuario_id and not solicitante_nome:
            flash('Selecione um usuário ou preencha os dados do solicitante manualmente!', 'warning')
            return redirect(url_for('padrao.emprestimos'))
        
        if not equipamentos or len(equipamentos) == 0:
            flash('Adicione pelo menos um equipamento ao empréstimo!', 'warning')
            return redirect(url_for('padrao.emprestimos'))
        
        # Converter datas
        from datetime import datetime
        data_emprestimo = datetime.strptime(data_emprestimo_str, '%Y-%m-%d')
        data_previsao = datetime.strptime(data_previsao_str, '%Y-%m-%d')
        
        # Obter grupo_id da URL ou do formulário
        grupo_id = request.form.get('grupo_id') or request.args.get('grupo_id')
        if not grupo_id:
            flash('Grupo não identificado!', 'danger')
            return redirect(url_for('padrao.emprestimos'))
        
        # Criar empréstimo
        novo_emp = Emprestimo(
            grupo_id=int(grupo_id),
            usuario_id=int(usuario_id) if usuario_id else None,
            solicitante_nome=solicitante_nome if solicitante_nome else None,
            solicitante_matricula=solicitante_matricula if solicitante_matricula else None,
            solicitante_cargo=solicitante_cargo if solicitante_cargo else None,
            solicitante_unidade=solicitante_unidade if solicitante_unidade else None,
            solicitante_ramal=solicitante_ramal if solicitante_ramal else None,
            data_previsao_devolucao=data_previsao,
            criado_por_id=current_user.id,  # Quem registrou o empréstimo
            observacao=observacao,
            data_emprestimo=data_emprestimo
        )
        
        db.session.add(novo_emp)
        db.session.flush()  # Para obter o ID do empréstimo
        
        # Adicionar equipamentos
        for i, equipamento in enumerate(equipamentos):
            if equipamento.strip():  # Ignorar vazios
                patrimonio = patrimonios[i] if i < len(patrimonios) else None
                equip = EmprestimoEquipamento(
                    emprestimo_id=novo_emp.id,
                    equipamento=equipamento.strip(),
                    patrimonio=patrimonio.strip() if patrimonio else None
                )
                db.session.add(equip)
        
        db.session.commit()
        flash('Empréstimo registrado com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar empréstimo: {str(e)}', 'danger')
    
    return redirect(url_for('padrao.emprestimos'))


@padrao_blue.route('/emprestimos/<int:emprestimo_id>/devolver', methods=['POST'])
@login_required
def devolver_emprestimo(emprestimo_id):
    """
    Registrar devolução de empréstimo
    """
    try:
        emprestimo = Emprestimo.query.get_or_404(emprestimo_id)
        
        # Obter observação de quem devolveu
        obs_devolucao = request.form.get('obs_devolucao', '').strip()
        
        if not obs_devolucao:
            flash('É obrigatório informar quem devolveu o equipamento!', 'warning')
            return redirect(url_for('padrao.emprestimos'))
        
        # Atualizar status e data de devolução
        from datetime import datetime
        emprestimo.status = 'Devolvido'
        emprestimo.data_devolucao_real = datetime.now()
        emprestimo.devolvido_por_id = current_user.id  # Registrar quem recebeu a devolução
        emprestimo.data_devolucao_registro = datetime.now()
        emprestimo.observacao = obs_devolucao  # Salvar quem devolveu na observação
        
        db.session.commit()
        flash('Devolução registrada com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar devolução: {str(e)}', 'danger')
    
    return redirect(url_for('padrao.emprestimos'))


@padrao_blue.route('/emprestimos/<int:emprestimo_id>/relatorio')
@login_required
def relatorio_emprestimo(emprestimo_id):
    """
    Gerar relatório de empréstimo (Termo de Responsabilidade)
    """
    try:
        emprestimo = Emprestimo.query.options(
            joinedload(Emprestimo.equipamentos),
            joinedload(Emprestimo.grupo),
            joinedload(Emprestimo.criado_por),
            joinedload(Emprestimo.usuario)
        ).get_or_404(emprestimo_id)
        
        # Verificar permissão de acesso
        if current_user.perfil.nome not in ['Administrador', 'Tecnico', 'Tecnico_adm']:
            flash('Você não tem permissão para acessar este relatório.', 'danger')
            return redirect(url_for('padrao.emprestimos'))
        
        # Verificar se o usuário pertence ao grupo do empréstimo
        if current_user.perfil.nome != 'Administrador':
            if emprestimo.grupo not in getattr(current_user, 'grupos_tecnicos', []):
                flash('Você não tem permissão para acessar este relatório.', 'danger')
                return redirect(url_for('padrao.emprestimos'))
        
        return render_template('relatorio.html', emprestimo=emprestimo)
        
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
        return redirect(url_for('padrao.emprestimos'))
    
@padrao_blue.route('/api/chamado/<int:chamado_id>/info', methods=['GET'])
@login_required
def api_chamado_info(chamado_id):
    try:
        # Importe local para evitar erros circulares
        from servicos.model import Chamado
        
        chamado = Chamado.query.get_or_404(chamado_id)
        
        # Pega o nome do técnico ou retorna None
        nome_tecnico = None
        if chamado.tecnico_responsavel:
            nome_tecnico = chamado.tecnico_responsavel.nome or chamado.tecnico_responsavel.nome_usuario
            
        return jsonify({
            'id': chamado.id,
            'status': chamado.status.nome,
            'tecnico': nome_tecnico
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@padrao_blue.route('/api/demandas/status_lista', methods=['POST'])
@login_required
def api_status_demandas_lista():
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify([])

        # Use joinedload para carregar o técnico e evitar querys extras
        chamados = Chamado.query.options(
            joinedload(Chamado.tecnico_responsavel)
        ).filter(Chamado.id.in_(ids)).all()
        
        resultado = []
        for c in chamados:
            status_nome = c.status.nome
            
            # Cores do Status
            badge_class = 'badge-info'
            if status_nome == 'Em Andamento': badge_class = 'badge-primary'
            elif status_nome == 'Finalizado': badge_class = 'badge-success'
            elif status_nome == 'Cancelado': badge_class = 'badge-danger'
            elif status_nome == 'Reaberto': badge_class = 'badge-warning'
            elif status_nome == 'Suspensa': badge_class = 'badge-secondary'
            
            # Dados do Técnico
            tecnico_nome = None
            if c.tecnico_responsavel:
                tecnico_nome = c.tecnico_responsavel.nome or c.tecnico_responsavel.nome_usuario
            
            resultado.append({
                'id': c.id,
                'status': status_nome,
                'badge_class': badge_class,
                'pode_avaliar': (status_nome == 'Finalizado'),
                'avaliacao': c.avaliacao,
                'tecnico': tecnico_nome # NOVO CAMPO
            })
            
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500