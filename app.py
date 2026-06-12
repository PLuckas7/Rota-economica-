from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import random
import math

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rota-economica-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rota_economica.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ─────────────────────────────────────────────
#  MODELS
# ─────────────────────────────────────────────

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    cidade = db.Column(db.String(100))
    pais = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    avaliacoes = db.relationship('Avaliacao', backref='usuario', lazy=True)
    alertas = db.relationship('AlertaPreco', backref='usuario', lazy=True)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Posto(db.Model):
    __tablename__ = 'postos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    bandeira = db.Column(db.String(80))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    telefone = db.Column(db.String(20))
    horario = db.Column(db.String(60))
    precos = db.relationship('Preco', backref='posto', lazy=True, cascade='all, delete-orphan')
    avaliacoes = db.relationship('Avaliacao', backref='posto', lazy=True, cascade='all, delete-orphan')

    @property
    def media_avaliacao(self):
        if not self.avaliacoes:
            return 0
        return round(sum(a.nota for a in self.avaliacoes) / len(self.avaliacoes), 1)

    @property
    def preco_atual_gasolina(self):
        p = Preco.query.filter_by(posto_id=self.id, tipo='gasolina').order_by(Preco.atualizado_em.desc()).first()
        return p.valor if p else None

    @property
    def preco_atual_etanol(self):
        p = Preco.query.filter_by(posto_id=self.id, tipo='etanol').order_by(Preco.atualizado_em.desc()).first()
        return p.valor if p else None

    @property
    def preco_atual_diesel(self):
        p = Preco.query.filter_by(posto_id=self.id, tipo='diesel').order_by(Preco.atualizado_em.desc()).first()
        return p.valor if p else None

    def distancia(self, lat, lon):
        R = 6371
        dlat = math.radians(self.latitude - lat)
        dlon = math.radians(self.longitude - lon)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(self.latitude)) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def to_dict(self, user_lat=None, user_lon=None):
        d = {
            'id': self.id,
            'nome': self.nome,
            'endereco': self.endereco,
            'bandeira': self.bandeira,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'telefone': self.telefone,
            'horario': self.horario,
            'media_avaliacao': self.media_avaliacao,
            'total_avaliacoes': len(self.avaliacoes),
            'gasolina': self.preco_atual_gasolina,
            'etanol': self.preco_atual_etanol,
            'diesel': self.preco_atual_diesel,
        }
        if user_lat and user_lon:
            d['distancia'] = round(self.distancia(user_lat, user_lon), 2)
        return d


class Preco(db.Model):
    __tablename__ = 'precos'
    id = db.Column(db.Integer, primary_key=True)
    posto_id = db.Column(db.Integer, db.ForeignKey('postos.id'), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)  # gasolina, etanol, diesel
    valor = db.Column(db.Float, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Avaliacao(db.Model):
    __tablename__ = 'avaliacoes'
    id = db.Column(db.Integer, primary_key=True)
    posto_id = db.Column(db.Integer, db.ForeignKey('postos.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nota = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class AlertaPreco(db.Model):
    __tablename__ = 'alertas_preco'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    posto_id = db.Column(db.Integer, db.ForeignKey('postos.id'), nullable=False)
    tipo = db.Column(db.String(30))
    preco_limite = db.Column(db.Float)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ─────────────────────────────────────────────
#  ROUTES – Auth
# ─────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('mapa'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('mapa'))
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        user = Usuario.query.filter_by(email=email).first()
        if user and user.check_senha(senha):
            login_user(user)
            return redirect(url_for('mapa'))
        flash('Email ou senha incorretos.', 'error')
    return render_template('login.html')


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        cidade = request.form.get('cidade')
        pais = request.form.get('pais')
        if Usuario.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'error')
            return render_template('cadastro.html')
        user = Usuario(nome=nome, email=email, cidade=cidade, pais=pais)
        user.set_senha(senha)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('mapa'))
    return render_template('cadastro.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ─────────────────────────────────────────────
#  ROUTES – Pages
# ─────────────────────────────────────────────

@app.route('/mapa')
@login_required
def mapa():
    return render_template('mapa.html')


@app.route('/postos')
@login_required
def postos():
    return render_template('postos.html')


@app.route('/comparacao')
@login_required
def comparacao():
    return render_template('comparacao.html')


@app.route('/alertas')
@login_required
def alertas():
    meus_alertas = AlertaPreco.query.filter_by(usuario_id=current_user.id).all()
    todos_postos = Posto.query.all()
    return render_template('alertas.html', alertas=meus_alertas, postos=todos_postos)


@app.route('/perfil')
@login_required
def perfil():
    minhas_avals = Avaliacao.query.filter_by(usuario_id=current_user.id).order_by(Avaliacao.criado_em.desc()).all()
    return render_template('perfil.html', avaliacoes=minhas_avals)


@app.route('/suporte')
@login_required
def suporte():
    return render_template('suporte.html')

# ─────────────────────────────────────────────
#  API – Postos
# ─────────────────────────────────────────────

@app.route('/api/postos')
@login_required
def api_postos():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    raio = request.args.get('raio', 10, type=float)
    combustivel = request.args.get('combustivel', '')
    ordem = request.args.get('ordem', 'distancia')

    postos = Posto.query.all()

    resultado = []
    for p in postos:
        d = p.to_dict(lat, lon)
        if combustivel and d.get(combustivel) is None:
            continue
        if lat and lon and d.get('distancia', 0) > raio:
            continue
        resultado.append(d)

    if ordem == 'preco' and combustivel:
        resultado.sort(key=lambda x: x.get(combustivel) or 9999)
    elif ordem == 'avaliacao':
        resultado.sort(key=lambda x: x['media_avaliacao'], reverse=True)
    elif lat and lon:
        resultado.sort(key=lambda x: x.get('distancia', 9999))

    return jsonify(resultado)


@app.route('/api/postos/<int:posto_id>')
@login_required
def api_posto_detalhe(posto_id):
    posto = Posto.query.get_or_404(posto_id)
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    data = posto.to_dict(lat, lon)

    historico = {}
    for tipo in ['gasolina', 'etanol', 'diesel']:
        registros = Preco.query.filter_by(posto_id=posto_id, tipo=tipo)\
            .order_by(Preco.atualizado_em.desc()).limit(7).all()
        historico[tipo] = [{'data': r.atualizado_em.strftime('%d/%m'), 'valor': r.valor} for r in reversed(registros)]

    avals = []
    for a in posto.avaliacoes[-5:]:
        avals.append({
            'nota': a.nota,
            'comentario': a.comentario,
            'usuario': a.usuario.nome,
            'data': a.criado_em.strftime('%d/%m/%Y')
        })

    data['historico'] = historico
    data['avaliacoes'] = avals
    return jsonify(data)


@app.route('/api/avaliar', methods=['POST'])
@login_required
def api_avaliar():
    dados = request.json
    posto_id = dados.get('posto_id')
    nota = dados.get('nota')
    comentario = dados.get('comentario', '')

    existente = Avaliacao.query.filter_by(posto_id=posto_id, usuario_id=current_user.id).first()
    if existente:
        existente.nota = nota
        existente.comentario = comentario
        existente.criado_em = datetime.utcnow()
    else:
        av = Avaliacao(posto_id=posto_id, usuario_id=current_user.id, nota=nota, comentario=comentario)
        db.session.add(av)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/alertas', methods=['POST'])
@login_required
def api_criar_alerta():
    dados = request.json
    alerta = AlertaPreco(
        usuario_id=current_user.id,
        posto_id=dados['posto_id'],
        tipo=dados['tipo'],
        preco_limite=dados['preco_limite']
    )
    db.session.add(alerta)
    db.session.commit()
    return jsonify({'ok': True, 'id': alerta.id})


@app.route('/api/alertas/<int:alerta_id>', methods=['DELETE'])
@login_required
def api_deletar_alerta(alerta_id):
    alerta = AlertaPreco.query.filter_by(id=alerta_id, usuario_id=current_user.id).first_or_404()
    db.session.delete(alerta)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/comparar')
@login_required
def api_comparar():
    ids = request.args.get('ids', '')
    if not ids:
        return jsonify([])
    id_list = [int(i) for i in ids.split(',') if i.strip().isdigit()]
    postos = Posto.query.filter(Posto.id.in_(id_list)).all()
    return jsonify([p.to_dict() for p in postos])


@app.route('/api/notificacoes')
@login_required
def api_notificacoes():
    alertas = AlertaPreco.query.filter_by(usuario_id=current_user.id, ativo=True).all()
    notifs = []
    for alerta in alertas:
        posto = Posto.query.get(alerta.posto_id)
        if posto:
            preco_atual = getattr(posto, f'preco_atual_{alerta.tipo}')
            if preco_atual and preco_atual <= alerta.preco_limite:
                notifs.append({
                    'mensagem': f'{posto.nome}: {alerta.tipo} a R$ {preco_atual:.2f} (abaixo do seu alerta de R$ {alerta.preco_limite:.2f})',
                    'posto_id': posto.id
                })
    return jsonify(notifs)


# ─────────────────────────────────────────────
#  ADMIN – decorator & routes
# ─────────────────────────────────────────────

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acesso restrito a administradores.', 'error')
            return redirect(url_for('mapa'))
        return f(*args, **kwargs)
    return decorated


@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_usuarios = Usuario.query.count()
    total_postos = Posto.query.count()
    total_avaliacoes = Avaliacao.query.count()
    total_alertas = AlertaPreco.query.count()

    sete_dias = datetime.utcnow() - timedelta(days=7)
    novos_usuarios = Usuario.query.filter(Usuario.criado_em >= sete_dias).count()

    from sqlalchemy import func
    cidades = db.session.query(Usuario.cidade, func.count(Usuario.id).label('total'))\
        .group_by(Usuario.cidade).order_by(func.count(Usuario.id).desc()).limit(5).all()

    precos_medios = {}
    for tipo in ['gasolina', 'etanol', 'diesel']:
        subq = db.session.query(
            Preco.posto_id,
            func.max(Preco.atualizado_em).label('max_data')
        ).filter(Preco.tipo == tipo).group_by(Preco.posto_id).subquery()
        media = db.session.query(func.avg(Preco.valor)).join(
            subq, db.and_(Preco.posto_id == subq.c.posto_id, Preco.atualizado_em == subq.c.max_data)
        ).filter(Preco.tipo == tipo).scalar()
        precos_medios[tipo] = round(float(media), 2) if media else 0

    ultimas_avals = Avaliacao.query.order_by(Avaliacao.criado_em.desc()).limit(5).all()

    return render_template('admin.html',
        total_usuarios=total_usuarios,
        total_postos=total_postos,
        total_avaliacoes=total_avaliacoes,
        total_alertas=total_alertas,
        novos_usuarios=novos_usuarios,
        cidades=cidades,
        precos_medios=precos_medios,
        ultimas_avals=ultimas_avals,
    )


@app.route('/admin/usuarios')
@login_required
@admin_required
def admin_usuarios():
    q = request.args.get('q', '')
    query = Usuario.query
    if q:
        query = query.filter(
            db.or_(Usuario.nome.ilike(f'%{q}%'), Usuario.email.ilike(f'%{q}%'))
        )
    usuarios = query.order_by(Usuario.criado_em.desc()).all()
    return render_template('admin_usuarios.html', usuarios=usuarios, q=q)


@app.route('/admin/usuarios/<int:uid>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_editar_usuario(uid):
    usuario = Usuario.query.get_or_404(uid)
    if request.method == 'POST':
        usuario.nome = request.form.get('nome', usuario.nome)
        usuario.email = request.form.get('email', usuario.email)
        usuario.cidade = request.form.get('cidade', usuario.cidade)
        usuario.pais = request.form.get('pais', usuario.pais)
        usuario.is_admin = request.form.get('is_admin') == 'on'
        nova_senha = request.form.get('nova_senha', '').strip()
        if nova_senha:
            usuario.set_senha(nova_senha)
        db.session.commit()
        flash(f'Usuário {usuario.nome} atualizado com sucesso.', 'success')
        return redirect(url_for('admin_usuarios'))
    return render_template('admin_editar_usuario.html', usuario=usuario)


@app.route('/admin/usuarios/<int:uid>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_excluir_usuario(uid):
    if uid == current_user.id:
        flash('Você não pode excluir sua própria conta admin.', 'error')
        return redirect(url_for('admin_usuarios'))
    usuario = Usuario.query.get_or_404(uid)
    Avaliacao.query.filter_by(usuario_id=uid).delete()
    AlertaPreco.query.filter_by(usuario_id=uid).delete()
    db.session.delete(usuario)
    db.session.commit()
    flash(f'Usuário {usuario.nome} excluído.', 'success')
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/postos')
@login_required
@admin_required
def admin_postos():
    postos = Posto.query.order_by(Posto.nome).all()
    return render_template('admin_postos.html', postos=postos)


@app.route('/admin/postos/<int:pid>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_editar_posto(pid):
    posto = Posto.query.get_or_404(pid)
    if request.method == 'POST':
        posto.nome = request.form.get('nome', posto.nome)
        posto.endereco = request.form.get('endereco', posto.endereco)
        posto.bandeira = request.form.get('bandeira', posto.bandeira)
        posto.telefone = request.form.get('telefone', posto.telefone)
        posto.horario = request.form.get('horario', posto.horario)
        posto.latitude = float(request.form.get('latitude', posto.latitude))
        posto.longitude = float(request.form.get('longitude', posto.longitude))
        for tipo in ['gasolina', 'etanol', 'diesel']:
            val_str = request.form.get(f'preco_{tipo}', '').strip()
            if val_str:
                try:
                    val = float(val_str.replace(',', '.'))
                    novo = Preco(posto_id=posto.id, tipo=tipo, valor=val, atualizado_em=datetime.utcnow())
                    db.session.add(novo)
                except ValueError:
                    pass
        db.session.commit()
        flash(f'Posto {posto.nome} atualizado.', 'success')
        return redirect(url_for('admin_postos'))
    return render_template('admin_editar_posto.html', posto=posto)


@app.route('/admin/postos/<int:pid>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_excluir_posto(pid):
    posto = Posto.query.get_or_404(pid)
    nome = posto.nome
    db.session.delete(posto)
    db.session.commit()
    flash(f'Posto "{nome}" excluído.', 'success')
    return redirect(url_for('admin_postos'))


@app.route('/admin/avaliacoes')
@login_required
@admin_required
def admin_avaliacoes():
    avals = Avaliacao.query.order_by(Avaliacao.criado_em.desc()).all()
    return render_template('admin_avaliacoes.html', avaliacoes=avals)


@app.route('/admin/avaliacoes/<int:aid>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_excluir_avaliacao(aid):
    av = Avaliacao.query.get_or_404(aid)
    db.session.delete(av)
    db.session.commit()
    flash('Avaliação excluída.', 'success')
    return redirect(url_for('admin_avaliacoes'))

# ─────────────────────────────────────────────
#  SEED DATA
# ─────────────────────────────────────────────

def seed_data():
    if Posto.query.count() > 0:
        return

    # Postos reais de Caruaru-PE obtidos via Google Places API
    postos_data = [
        # ── Centro / Nossa Sra. das Dores ──
        {'nome': 'Posto Petrol', 'endereco': 'R. Floriano Peixoto, 70 - Nossa Sra. das Dores, Caruaru-PE', 'bandeira': 'Independente', 'lat': -8.2837867, 'lon': -35.9718296, 'tel': '(81) 99660-9005', 'horario': '24h'},
        {'nome': 'Posto Shell – R. Treze de Maio', 'endereco': 'R. Treze de Maio, 49 - Nossa Sra. das Dores, Caruaru-PE', 'bandeira': 'Shell', 'lat': -8.2868463, 'lon': -35.973399, 'tel': None, 'horario': '06h–23h'},
        {'nome': 'Posto América – Centro', 'endereco': 'R. Prof. Augusto Tabosa, 49 - Nossa Sra. das Dores, Caruaru-PE', 'bandeira': 'Independente', 'lat': -8.2868444, 'lon': -35.9733092, 'tel': '(81) 99981-0187', 'horario': '24h'},

        # ── Divinópolis ──
        {'nome': 'Posto Shell – Av. Rui Barbosa', 'endereco': 'Av. Rui Barbosa, 823 - Divinópolis, Caruaru-PE', 'bandeira': 'Shell', 'lat': -8.2761693, 'lon': -35.9801701, 'tel': None, 'horario': '24h'},
        {'nome': 'Posto Joaquim Nabuco', 'endereco': 'Av. Joaquim Nabuco, 450 - Divinópolis, Caruaru-PE', 'bandeira': 'Independente', 'lat': -8.278415, 'lon': -35.977619, 'tel': None, 'horario': '06h–22h'},
        {'nome': 'Posto São Luís', 'endereco': 'R. Paraense, 31 - Divinópolis, Caruaru-PE', 'bandeira': 'Independente', 'lat': -8.2759691, 'lon': -35.9824207, 'tel': '(81) 3137-8037', 'horario': '06h–22h'},

        # ── Indianópolis / São Francisco ──
        {'nome': 'Posto Petrobras – Indianópolis', 'endereco': 'Av. José Rodrigues de Jesus, 128 - Indianópolis, Caruaru-PE', 'bandeira': 'Petrobras', 'lat': -8.2883649, 'lon': -35.963782, 'tel': '(81) 0800-770-1337', 'horario': '24h'},
        {'nome': 'Posto Petrobras – Vera Cruz', 'endereco': 'Av. Vera Cruz, 500 - São Francisco, Caruaru-PE', 'bandeira': 'Petrobras', 'lat': -8.2883089, 'lon': -35.9790727, 'tel': '(81) 3731-3430', 'horario': '07h–22h'},
        {'nome': 'Auto Posto 07', 'endereco': 'R. Joaquim Távora, 432 - São Francisco, Caruaru-PE', 'bandeira': 'Independente', 'lat': -8.2884219, 'lon': -35.9785759, 'tel': None, 'horario': '24h'},

        # ── Caiuca / Kennedy ──
        {'nome': 'Posto Shell – Leão Dourado', 'endereco': 'Av. Leão Dourado, 382 - Caiuca, Caruaru-PE', 'bandeira': 'Shell', 'lat': -8.2881094, 'lon': -35.9848902, 'tel': None, 'horario': '06h–23h'},
        {'nome': 'Posto Shell + GNV – Kennedy', 'endereco': 'Av. Leão Dourado, 2365 - Kennedy, Caruaru-PE', 'bandeira': 'Shell', 'lat': -8.286724, 'lon': -36.0023879, 'tel': '(81) 3721-5879', 'horario': '24h'},

        # ── Nova Caruaru / BR-104 ──
        {'nome': 'Posto Petronunes + GNV', 'endereco': 'BR-104, 1180 - Nova Caruaru, Caruaru-PE', 'bandeira': 'Independente', 'lat': -8.2670339, 'lon': -35.9781536, 'tel': '(81) 3721-3191', 'horario': '24h'},

        # ── Universitário ──
        {'nome': 'Posto Shell – Av. Brasil', 'endereco': 'Av. Brasil, 1440 - Universitário, Caruaru-PE', 'bandeira': 'Shell', 'lat': -8.2618393, 'lon': -35.9576711, 'tel': None, 'horario': '06h–23h'},
    ]

    precos_base = {
        'gasolina': [5.79, 5.89, 5.85, 5.95, 5.82, 5.88, 5.99, 5.91, 5.84, 5.93, 5.75, 5.80, 5.97],
        'etanol':   [3.89, 3.99, 3.95, 4.05, 3.92, 3.98, 4.09, 4.01, 3.94, 4.03, 3.85, 3.90, 4.07],
        'diesel':   [6.19, 6.29, 6.25, 6.35, 6.22, 6.28, 6.39, 6.31, 6.24, 6.33, 6.15, 6.20, 6.37],
    }

    for i, pd_ in enumerate(postos_data):
        posto = Posto(
            nome=pd_['nome'], endereco=pd_['endereco'], bandeira=pd_['bandeira'],
            latitude=pd_['lat'], longitude=pd_['lon'],
            telefone=pd_['tel'], horario=pd_['horario']
        )
        db.session.add(posto)
        db.session.flush()

        for tipo, vals in precos_base.items():
            base = vals[i]
            for d in range(7):
                variacao = random.uniform(-0.05, 0.05)
                p = Preco(
                    posto_id=posto.id, tipo=tipo,
                    valor=round(base + variacao + (d * 0.01), 2),
                    atualizado_em=datetime.utcnow() - timedelta(days=6-d)
                )
                db.session.add(p)

    db.session.commit()
    print("✅ Dados de seed inseridos.")


# ─────────────────────────────────────────────
#  INIT
# ─────────────────────────────────────────────

with app.app_context():
    db.create_all()
    seed_data()
    # Criar admin padrão se não existir
    admin = Usuario.query.filter_by(email='admin@rotaeconomica.com').first()
    if not admin:
        admin = Usuario(
            nome='Administrador',
            email='admin@rotaeconomica.com',
            cidade='Caruaru',
            pais='Brasil',
            is_admin=True
        )
        admin.set_senha('Admin@2026')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin criado: admin@rotaeconomica.com / Admin@2026")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
