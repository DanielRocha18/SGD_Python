from servicos.model import *
from flask import request
from servicos import app
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os

def log(idUsuario, acao):
    log = Log(idUsuario, request.environ['REMOTE_ADDR'], acao)
    db.session.add(log)
    db.session.commit()

def logEmail(email, info):

    logEmail = LogEmail(email, info)
    db.session.add(logEmail)
    db.session.commit()

def enviarEmail(email, tipo):
    
    #configuracoes para o envio de emails
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Solicitação - Sistema de controle de telefonia e dados móveis"
    msg['From'] = "telefonia@sejus.df.gov.br"
    msg['To'] = email

    #define conteudo email
    html = None
    #se tipo 1 envia email de criacao da solicitacao para usuario final
    if tipo == 1:
        html = f"""\
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif;">
                <table cellpadding="0" cellspacing="0" width="100%" style="background: #f4f4f4;">
                    <tr>
                        <td align="center" style="padding: 20px;">
                            <table width="600" cellpadding="0" cellspacing="0" style="background: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <tr>
                                    <td style="background: #0061AE; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                                        <h2 style="color: #fff; margin: 0; font-size: 18px;">Sistema de Telefonia e Dados Móveis</h2>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 30px;">
                                        <p style="color: #333; margin: 0 0 15px;">Prezado(a) Servidor(a),</p>
                                        <p style="color: #333; margin: 0 0 15px;">Sua solicitação foi realizada com sucesso!</p>
                                        <p style="color: #333; margin: 0 0 10px;"><strong>Próximos passos:</strong></p>
                                        <ol style="color: #333; margin: 0 0 15px; padding-left: 20px;">
                                            <li>Assinar e obter assinatura do superior em <a href="https://telefonia.sejus.df.gov.br" style="color: #0061AE;">telefonia.sejus.df.gov.br</a></li>
                                            <li>Aguardar validação do gestor</li>
                                            <li>Retirar aparelho e assinar Termo de Recebimento</li>
                                        </ol>
                                        <p style="color: #666; font-size: 12px; margin: 15px 0 0; border-top: 1px solid #eee; padding-top: 15px;">
                                            <strong>UNITEC</strong><br>
                                            Este é um e-mail automático, não responda.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            """
    else:
        html = f""

    #faz o envio do email
    conteudo = MIMEText(html, 'html')
    msg.attach(conteudo)
    s = smtplib.SMTP('localhost')
    s.sendmail("telefonia@sejus.df.gov.br", email, msg.as_string().encode('utf-8'))
    s.quit()
    print(f"Envio de email para {email}")


def enviarEmailNovaDemanda(tecnicos_emails, dados_demanda):
    """
    Envia email para técnicos notificando sobre nova demanda
    Usa o mesmo padrão da função enviarEmail() existente
    """
    
    # Configurações para o envio de emails
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Transferida - Ticket: {dados_demanda['numero_ticket']}-{dados_demanda['ano']}"
    msg['From'] = "central@sejus.df.gov.br"
    msg['To'] = ", ".join(tecnicos_emails)
    
    # Formata informações opcionais
    info_unidade = f"<br><small>({dados_demanda.get('unidade', '')})</small>" if dados_demanda.get('unidade') else ""
    
    # Define conteúdo do email (mesmo estilo da função enviarEmail)
    html = f"""\
<body style="margin: 0; padding: 0; font-family: 'Open Sans', sans-serif;">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400&display=swap');
    </style>
    <table cellpadding="0" cellspacing="0" width="100%">
        <tr>
            <td>
                <table align="center" cellpadding="0" cellspacing="0" width="600"
                    style="border-collapse: collapse;">
                    <tr style="background: #E5E5E5;">
                        <td align="center" bgcolor="#E5E5E5" style="padding: 30px 0 15px 0;">
                            <div style="color: #0061AE; font-size: 20px; background: #FFFFFF; padding-top: 15px; padding-bottom: 15px; margin-left: 30px; margin-right: 30px; border-radius: 0.35rem;">
                                <h1 style="color: #0061AE; font-size: 20px;">Sistema de Gerenciamento de Demandas</h1>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td bgcolor="#E5E5E5" style="padding: 30px 30px 30px 30px;">
                            <table cellpadding="0" cellspacing="0" width="100%" style="background: #fff; padding: 30px; border-radius: 0.35rem;">
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;">Prezado (a) Servidor (a);</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><br>Uma nova demanda foi aberta na categoria Suporte Informática no Sistema de Demandas.</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><br><b>Ticket:</b> {dados_demanda['numero_ticket']}-{dados_demanda['ano']}</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><b>Data de Abertura:</b> {dados_demanda['data_abertura']}</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><br><b>Solicitante:</b> {dados_demanda['solicitante_nome']}{info_unidade}</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><b>E-mail:</b> <a href="mailto:{dados_demanda['solicitante_email']}" style="color: #035AA6;">{dados_demanda['solicitante_email']}</a></p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><br><b>Categoria:</b> {dados_demanda['categoria']}</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><br><b>Detalhamento:</b></p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;">{dados_demanda['detalhamento']}</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><br><b>Importante:</b> Esta mensagem foi enviada com prioridade Alta.</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><br>Atenciosamente,</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #035AA6;"><br>SIGEDEM</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <p style="text-align: left; color: #dc3545;"><br>Este é um e-mail automático, por favor não responda.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
"""
    
    # Faz o envio do email usando configurações do .env
    conteudo = MIMEText(html, 'html')
    msg.attach(conteudo)
    
    smtp_host = os.environ.get('SMTP_HOST', 'localhost')
    smtp_port = int(os.environ.get('SMTP_PORT', 25))
    smtp_use_tls = os.environ.get('SMTP_USE_TLS', 'False').lower() == 'true'
    smtp_username = os.environ.get('SMTP_USERNAME')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    
    # Aumenta timeout e adiciona tratamento de erro
    try:
        s = smtplib.SMTP(timeout=30)
        s.connect(smtp_host, smtp_port)
        s.ehlo('sejus.df.gov.br')  # Identifica como domínio SEJUS
        
        if smtp_use_tls:
            s.starttls()
            s.ehlo('sejus.df.gov.br')  # Re-identifica após TLS
        
        # Faz login se tiver usuário e senha
        if smtp_username and smtp_password:
            s.login(smtp_username, smtp_password)
        
        s.sendmail("central@sejus.df.gov.br", tecnicos_emails, msg.as_string())
        s.quit()
        
        print(f"✉️ Email de nova demanda enviado para: {', '.join(tecnicos_emails)}")
        print(f"📋 Ticket: {dados_demanda['numero_ticket']}-{dados_demanda['ano']}")
        print(f"📧 Via: {smtp_host}:{smtp_port}")
        return True
    except Exception as e:
        print(f"⚠️ Erro ao enviar email de notificação: {str(e)}")
        return False
