from servicos import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# ==================== TABELAS DO SISTEMA ====================

class Unidade(db.Model):
    """
    Tabela de unidades organizacionais (mantida para histórico)
    """
    __tablename__ = 'tb_unidade'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unidade = db.Column(db.String(60), nullable=False, unique=True)

    def __init__(self, unidade):
        self.unidade = unidade

    def __repr__(self):
        return f'<Unidade {self.unidade}>'


class Perfil(db.Model):
    """
    Tabela de perfis de usuários
    Ex: Administrador, Tecnico, Tecnico_adm, Padrao
    """
    __tablename__ = 'tb_perfis'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)

    # Relacionamentos
    usuarios = db.relationship('Usuario', backref='perfil', lazy=True)

    def __init__(self, nome):
        self.nome = nome

    def __repr__(self):
        return f'<Perfil {self.nome}>'


class Usuario(UserMixin, db.Model):
    """
    Tabela de usuários do sistema - Versão Local (Sem LDAP)
    """
    __tablename__ = 'tb_usuarios'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome_usuario = db.Column(db.String(200), nullable=False, unique=True)
    nome = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(200), nullable=False, unique=True)
    
    # NOVO CAMPO: Senha criptografada
    senha_hash = db.Column(db.String(255), nullable=False)
    
    cpf = db.Column(db.String(20), nullable=True)
    matricula = db.Column(db.String(9), nullable=True)
    telefone = db.Column(db.String(20), nullable=True)
    unidade_lotacao = db.Column(db.String(200), nullable=True)
    perfil_id = db.Column(db.Integer, db.ForeignKey('tb_perfis.id'), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)

    # ... (relacionamentos permanecem iguais)

    # Métodos para gerenciar a senha local
    def set_senha(self, senha):
        """Cria o hash da senha"""
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        """Verifica se a senha digitada confere com o hash"""
        return check_password_hash(self.senha_hash, senha)

    # REMOVA o @staticmethod tentar_login (que usava LDAP)

    def __init__(self, nome_usuario, email, senha, perfil_id, ativo=True):
        self.nome_usuario = nome_usuario
        self.email = email
        self.set_senha(senha) # Transforma a senha em hash no momento da criação
        self.perfil_id = perfil_id
        self.ativo = ativo

    def __repr__(self):
        return f'<Usuario {self.nome_usuario}>'

class Grupo(db.Model):
    """
    Tabela de grupos de atendimento
    """
    __tablename__ = 'tb_grupos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(200), nullable=False, unique=True)
    descricao = db.Column(db.Text)
    cor_borda = db.Column(db.String(7), default='#4e73df')
    icone = db.Column(db.String(50), default='fas fa-folder')
    emprestimo_ativo = db.Column(db.Boolean, default=False)

    # Relacionamentos
    categorias = db.relationship('Categoria', backref='grupo', lazy=True)

    def __init__(self, nome, descricao=None, cor_borda='#4e73df', icone='fas fa-folder-open', emprestimo_ativo=False):
        self.nome = nome
        self.descricao = descricao
        self.cor_borda = cor_borda
        self.icone = icone
        self.emprestimo_ativo = emprestimo_ativo


    def __repr__(self):
        return f'<Grupo {self.nome}>'


# Tabela associativa para relacionamento muitos-para-muitos entre Tecnicos e Grupos
class TecnicoGrupo(db.Model):
    """
    Tabela associativa entre técnicos e grupos
    """
    __tablename__ = 'tb_tecnicos_grupos'

    usuario_id = db.Column(db.Integer, db.ForeignKey('tb_usuarios.id'), primary_key=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey('tb_grupos.id'), primary_key=True)

    def __init__(self, usuario_id, grupo_id):
        self.usuario_id = usuario_id
        self.grupo_id = grupo_id


class Status(db.Model):
    """
    Tabela de status dos chamados
    Ex: Aberto, Em Andamento, Concluido, Cancelado
    """
    __tablename__ = 'tb_status'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)

    # Relacionamentos
    chamados = db.relationship('Chamado', backref='status', lazy=True)

    def __init__(self, nome):
        self.nome = nome

    def __repr__(self):
        return f'<Status {self.nome}>'


class Categoria(db.Model):
    """
    Tabela de categorias de serviços
    """
    __tablename__ = 'tb_categorias'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey('tb_grupos.id'), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    cor_borda = db.Column(db.String(7), default='#36b9cc')
    icone = db.Column(db.String(50), default='fas fa-folder-open')

    # Relacionamentos
    itens = db.relationship('Item', backref='categoria', lazy=True)
    chamados = db.relationship('Chamado', backref='subcategoria', lazy=True)

    # Constraint única composta (grupo_id + nome)
    __table_args__ = (
        db.UniqueConstraint('grupo_id', 'nome', name='uk_grupo_nome'),
    )

    def __init__(self, grupo_id, nome, descricao=None, cor_borda='#36b9cc', icone='fas fa-folder-open'):
        self.grupo_id = grupo_id
        self.nome = nome
        self.descricao = descricao
        self.cor_borda = cor_borda
        self.icone = icone

    def __repr__(self):
        return f'<Categoria {self.nome}>'


class Item(db.Model):
    """
    Tabela de itens de serviços (subcategorias)
    """
    __tablename__ = 'tb_itens'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('tb_categorias.id'), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    icone = db.Column(db.String(50), default='fas fa-cube')
    
    # MANTENHA APENAS A COR
    cor_borda = db.Column(db.String(7), default='#1cc88a')

    # Constraint única composta (categoria_id + nome)
    __table_args__ = (
        db.UniqueConstraint('categoria_id', 'nome', name='uk_itens_nome'),
    )

    # Atualize o __init__ também (remova o parâmetro ativo)
    def __init__(self, categoria_id, nome, descricao=None, cor_borda='#1cc88a', icone='fas fa-cube'):
        self.categoria_id = categoria_id
        self.nome = nome
        self.descricao = descricao
        self.cor_borda = cor_borda
        self.icone = icone

    def __repr__(self):
        return f'<Item {self.nome}>'


class Chamado(db.Model):
    """
    Tabela de chamados/solicitações
    """
    __tablename__ = 'tb_chamados'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    usuario_solicitante_id = db.Column(db.Integer, db.ForeignKey('tb_usuarios.id'), nullable=False)
    subcategoria_id = db.Column(db.Integer, db.ForeignKey('tb_categorias.id'), nullable=False)
    status_id = db.Column(db.Integer, db.ForeignKey('tb_status.id'), nullable=False, default=1)
    tecnico_responsavel_id = db.Column(db.Integer, db.ForeignKey('tb_usuarios.id'))
    data_abertura = db.Column(db.DateTime, default=datetime.now)
    data_ultima_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    data_fechamento = db.Column(db.DateTime)
    anexo_filepath = db.Column(db.String(500), nullable=True)
    # Campo para demandas agrupadas (hierarquia pai-filho)
    chamado_pai_id = db.Column(db.Integer, db.ForeignKey('tb_chamados.id'), nullable=True)

    avaliacao = db.Column(db.Integer, nullable=True) # 1 a 5
    comentario_avaliacao = db.Column(db.Text, nullable=True)

    # Relacionamentos
    historico = db.relationship('HistoricoChamado', backref='chamado', lazy=True)
    
    # Relacionamento self-referencial para demandas agrupadas
    subchamados = db.relationship('Chamado', 
                                   backref=db.backref('chamado_pai', remote_side=[id]),
                                   lazy='dynamic')
    
    solicitante = db.relationship('Usuario', foreign_keys=[usuario_solicitante_id], backref='demandas_solicitadas')
    tecnico_responsavel = db.relationship('Usuario', foreign_keys=[tecnico_responsavel_id], backref='demandas_atendidas')
    
    def get_descricao_limpa(self):
        """
        Retorna a descrição sem os cabeçalhos/rodapés técnicos do formulário.
        Remove linhas que começam com '---'.
        """
        if not self.descricao:
            return ""
            
        linhas = self.descricao.split('\n')
        linhas_limpas = []
        
        for linha in linhas:
            # Ignora as linhas decorativas do sistema
            if linha.strip().startswith('---'):
                continue
            # Ignora linhas vazias repetidas (opcional, mas melhora o visual)
            if not linha.strip() and (not linhas_limpas or not linhas_limpas[-1].strip()):
                continue
            
            linhas_limpas.append(linha)
            
        return '\n'.join(linhas_limpas).strip()

    def __init__(self, titulo, descricao, usuario_solicitante_id, subcategoria_id, status_id=1, tecnico_responsavel_id=None, anexo_filepath=None, chamado_pai_id=None, avaliacao=None, comentario_avaliacao=None):
        self.titulo = titulo
        self.descricao = descricao
        self.usuario_solicitante_id = usuario_solicitante_id
        self.subcategoria_id = subcategoria_id
        self.status_id = status_id
        self.tecnico_responsavel_id = tecnico_responsavel_id
        self.anexo_filepath = anexo_filepath
        self.chamado_pai_id = chamado_pai_id
        self.avaliacao = avaliacao
        self.comentario_avaliacao = comentario_avaliacao

    def __repr__(self):
        return f'<Chamado {self.id} - {self.titulo}>'
    
class Formulario(db.Model):
    __tablename__ = 'tb_formularios'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    titulo = db.Column(db.String(200), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('tb_itens.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    descricao = db.Column(db.Text, nullable=True)

    # Relacionamentos
    item = db.relationship('Item', backref='formularios', lazy=True)
    campos = db.relationship('CampoFormulario', backref='formulario', lazy=True, cascade="all, delete-orphan")

    def __init__(self, titulo, item_id, descricao=None, ativo=True):
        self.titulo = titulo
        self.item_id = item_id
        self.descricao = descricao
        self.ativo = ativo

class CampoFormulario(db.Model):
    __tablename__ = 'tb_campos_formulario'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    formulario_id = db.Column(db.Integer, db.ForeignKey('tb_formularios.id'), nullable=False)
    label = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(200), default='text') # text, textarea, date, number
    obrigatorio = db.Column(db.Boolean, default=False)
    ordem = db.Column(db.Integer, default=0)

    def __init__(self, formulario_id, label, tipo='text', obrigatorio=False, ordem=0):
        self.formulario_id = formulario_id
        self.label = label
        self.tipo = tipo
        self.obrigatorio = obrigatorio
        self.ordem = ordem


class Comentario(db.Model):
    __tablename__ = 'tb_comentarios'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chamado_id = db.Column(db.Integer, db.ForeignKey('tb_chamados.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('tb_usuarios.id'), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    data_envio = db.Column(db.DateTime, default=datetime.now)
    
    # --- MUDANÇA: Novo campo de anexo ---
    anexo_filepath = db.Column(db.String(500), nullable=True)

    # Relacionamentos
    usuario = db.relationship('Usuario', backref='comentarios', lazy=True)
    chamado = db.relationship('Chamado', backref=db.backref('comentarios_chat', lazy=True))

    # --- MUDANÇA: Atualizado o __init__ ---
    def __init__(self, chamado_id, usuario_id, texto, anexo_filepath=None):
        self.chamado_id = chamado_id
        self.usuario_id = usuario_id
        self.texto = texto
        self.anexo_filepath = anexo_filepath

    def __repr__(self):
        return f'<Comentario {self.id} - Chamado {self.chamado_id}>'


class HistoricoChamado(db.Model):
    """
    Tabela de histórico de interações dos chamados
    """
    __tablename__ = 'tb_historico_chamado'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chamado_id = db.Column(db.Integer, db.ForeignKey('tb_chamados.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('tb_usuarios.id'), nullable=False)
    tipo_interacao = db.Column(db.String(50), nullable=False)  # Ex: Comentario, Mudanca_Status, Atribuicao_Tecnico
    detalhes = db.Column(db.Text, nullable=False)
    data_interacao = db.Column(db.DateTime, default=datetime.now)
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])

    def __init__(self, chamado_id, usuario_id, tipo_interacao, detalhes):
        self.chamado_id = chamado_id
        self.usuario_id = usuario_id
        self.tipo_interacao = tipo_interacao
        self.detalhes = detalhes

    def __repr__(self):
        return f'<HistoricoChamado {self.id} - {self.tipo_interacao}>'

class Log(db.Model):

    __tablename__ = "log"

    id = db.Column(db.Integer, primary_key=True)
    cpf_usuario = db.Column(db.String(255))
    ip = db.Column(db.String(50))
    acao = db.Column(db.Text(300))
    datahora = db.Column(db.DateTime, default=datetime.now)

    def __init__(self, cpf_usuario, ip, acao):
        self.cpf_usuario = cpf_usuario
        self.ip = ip
        self.acao = acao

    def __repr__(self):
        return self.acao

class LogEmail(db.Model):

    __tablename__ = "log_email"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200))
    info = db.Column(db.String(255))
    datahora = db.Column(db.DateTime, default=datetime.now)
    
    def __init__(self, email, info):
        self.email = email
        self.info = info

    def __repr__(self):
        return self.id



################### MODELOS DE EMPRÉSTIMOS ###################

class Emprestimo(db.Model):
    """
    Tabela de empréstimos
    """
    __tablename__ = 'tb_emprestimos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey('tb_grupos.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('tb_usuarios.id'), nullable=True)
    solicitante_nome = db.Column(db.String(200), nullable=True)
    solicitante_matricula = db.Column(db.String(20), nullable=True)
    solicitante_cargo = db.Column(db.String(200), nullable=True)
    solicitante_unidade = db.Column(db.String(200), nullable=True)
    solicitante_ramal = db.Column(db.String(50), nullable=True)
    data_emprestimo = db.Column(db.DateTime, nullable=False, default=datetime.now)
    data_previsao_devolucao = db.Column(db.DateTime, nullable=False)
    data_devolucao_real = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Ativo')  # Ativo, Devolvido, Atrasado
    observacao = db.Column(db.Text, nullable=True)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('tb_usuarios.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    devolvido_por_id = db.Column(db.Integer, db.ForeignKey('tb_usuarios.id'), nullable=True)
    data_devolucao_registro = db.Column(db.DateTime, nullable=True)

    # Relacionamentos
    grupo = db.relationship('Grupo', foreign_keys=[grupo_id], backref='emprestimos')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='emprestimos_recebidos')
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id], backref='emprestimos_criados')
    devolvido_por = db.relationship('Usuario', foreign_keys=[devolvido_por_id], backref='emprestimos_devolvidos')
    equipamentos = db.relationship('EmprestimoEquipamento', backref='emprestimo', lazy=True, cascade='all, delete-orphan')

    def __init__(self, grupo_id, data_previsao_devolucao, criado_por_id, usuario_id=None, solicitante_nome=None, 
                 solicitante_matricula=None, solicitante_cargo=None, solicitante_unidade=None, solicitante_ramal=None, observacao=None, data_emprestimo=None):
        self.grupo_id = grupo_id
        self.usuario_id = usuario_id
        self.solicitante_nome = solicitante_nome
        self.solicitante_matricula = solicitante_matricula
        self.solicitante_cargo = solicitante_cargo
        self.solicitante_unidade = solicitante_unidade
        self.solicitante_ramal = solicitante_ramal
        self.data_previsao_devolucao = data_previsao_devolucao
        self.criado_por_id = criado_por_id
        self.observacao = observacao
        if data_emprestimo:
            self.data_emprestimo = data_emprestimo

    def get_solicitante_nome(self):
        """Retorna o nome do solicitante (do usuário ou manual)"""
        if self.usuario:
            return self.usuario.nome
        return self.solicitante_nome or 'Não informado'
    
    def __repr__(self):
        return f'<Emprestimo {self.id} - {self.get_solicitante_nome()}>'


class EmprestimoEquipamento(db.Model):
    """
    Tabela de equipamentos vinculados a empréstimos (relação N para N)
    """
    __tablename__ = 'tb_emprestimos_equipamentos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    emprestimo_id = db.Column(db.Integer, db.ForeignKey('tb_emprestimos.id'), nullable=False)
    equipamento = db.Column(db.String(200), nullable=False)  # Nome/descrição do equipamento
    patrimonio = db.Column(db.String(50), nullable=True)  # Número de patrimônio (opcional)

    def __init__(self, emprestimo_id, equipamento, patrimonio=None):
        self.emprestimo_id = emprestimo_id
        self.equipamento = equipamento
        self.patrimonio = patrimonio

    def __repr__(self):
        return f'<EmprestimoEquipamento {self.equipamento}>'


################### modelo do servidor corporativo  ###################

class Servidor(db.Model):

    __bind_key__ = 'corporativo'
    __tablename__ = "tb_servidor"

    CPF = db.Column(db.String(11), primary_key=True)
    matr = db.Column(db.String(9))
    nome_servidor = db.Column(db.String(150))
    sexo = db.Column(db.Integer)
    sexo_desc = db.Column(db.String(75))
    carga_h = db.Column(db.Integer)
    status = db.Column(db.Integer)
    status_desc = db.Column(db.Integer)
    dt_admissao = db.Column(db.DateTime)
    dt_deslig = db.Column(db.DateTime)
    sit_funcional = db.Column(db.Integer)
    sit_funcional_desc = db.Column(db.String(100))
    cargo_efet_temp = db.Column(db.String(100))
    funcao = db.Column(db.String(100))
    r_f = db.Column(db.String(10))
    nr = db.Column(db.Integer)
    lotacao = db.Column(db.String(20))
    lotacao_desc = db.Column(db.String(200))

    def __repr__(self):
        return self.nome_servidor