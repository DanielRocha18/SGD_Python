"""
Script de migração para adicionar novos campos à tabela tb_usuarios
Execute este script apenas UMA vez após atualizar o modelo Usuario
"""
import sys
sys.dont_write_bytecode = True
from servicos import app, db
from sqlalchemy import text

def verificar_coluna_existe(nome_coluna):
    """Verifica se uma coluna já existe na tabela tb_usuarios"""
    try:
        query = text("""
            SELECT COUNT(*) as existe 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'tb_usuarios' 
            AND COLUMN_NAME = :coluna
        """)
        result = db.session.execute(query, {'coluna': nome_coluna}).fetchone()
        return result[0] > 0
    except Exception as e:
        print(f"Erro ao verificar coluna {nome_coluna}: {e}")
        return False

def adicionar_campos_usuario():
    """
    Adiciona os campos matricula, telefone, unidade_lotacao e login_rede
    à tabela tb_usuarios se eles não existirem
    """
    try:
        with app.app_context():
            # Lista de campos a adicionar: (nome_coluna, tipo, descrição)
            campos = [
                ('matricula', 'VARCHAR(9)', 'Matrícula do servidor'),
                ('telefone', 'VARCHAR(20)', 'Telefone/Ramal'),
                ('unidade_lotacao', 'VARCHAR(200)', 'Unidade de lotação'),
                ('login_rede', 'VARCHAR(100)', 'Login de rede')
            ]
            
            campos_adicionados = []
            campos_ja_existentes = []
            
            # Verifica e adiciona cada campo
            for nome_campo, tipo, descricao in campos:
                if verificar_coluna_existe(nome_campo):
                    campos_ja_existentes.append(nome_campo)
                    print(f"⚠ Campo '{nome_campo}' já existe na tabela")
                else:
                    try:
                        comando = text(f"ALTER TABLE tb_usuarios ADD COLUMN {nome_campo} {tipo};")
                        db.session.execute(comando)
                        campos_adicionados.append(f"{nome_campo} ({tipo})")
                        print(f"✓ Campo '{nome_campo}' adicionado com sucesso")
                    except Exception as e:
                        print(f"❌ Erro ao adicionar campo '{nome_campo}': {e}")
            
            db.session.commit()
            
            print("\n" + "=" * 60)
            print("✅ MIGRAÇÃO CONCLUÍDA!")
            print("=" * 60)
            
            if campos_adicionados:
                print("\n✓ Campos adicionados:")
                for campo in campos_adicionados:
                    print(f"  - {campo}")
            
            if campos_ja_existentes:
                print("\n⚠ Campos que já existiam:")
                for campo in campos_ja_existentes:
                    print(f"  - {campo}")
            
            if not campos_adicionados and not campos_ja_existentes:
                print("\n⚠ Nenhum campo foi processado")
            
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Erro durante a migração: {e}")
        return False
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRAÇÃO: Adicionar campos à tabela tb_usuarios")
    print("=" * 60)
    print("\nEste script irá adicionar os seguintes campos:")
    print("  - matricula")
    print("  - telefone")
    print("  - unidade_lotacao")
    print("  - login_rede")
    print("\n⚠ ATENÇÃO: Execute este script apenas UMA vez!")
    
    resposta = input("\nDeseja continuar? (s/n): ")
    
    if resposta.lower() == 's':
        adicionar_campos_usuario()
    else:
        print("\nMigração cancelada pelo usuário.")