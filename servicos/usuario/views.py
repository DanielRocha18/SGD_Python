from flask import render_template, url_for, request, redirect, session, Blueprint, flash, send_from_directory, send_file, make_response
from flask_login import login_required, current_user
from servicos.model import *
from servicos.functions import *
from servicos import app
import json

#cria blueprint da view
usuario_blue = Blueprint('usuario', __name__, template_folder='templates')

##############criacao das rotas de renderizacao##############



