# ⛽ Rota Econômica

**Projeto DEV RAP – UNIFAVIP Wyden**  
Disciplina: Desenvolvimento Rápido de Aplicações em Python  
Prof.: Dr. Kayo Henrique de Carvalho Monteiro  

**Equipe:** Pedro Luckas · Henrique Félix · Matheus Henrique · Pedro Arthur

---

## 📋 Descrição

Sistema web para direcionamento de abastecimento acessível. Permite que motoristas encontrem postos de gasolina próximos com os melhores preços, comparem combustíveis e recebam alertas de preço personalizados.

---

## 🚀 Como Executar

### 1. Instalar dependências
```bash
pip install flask flask-sqlalchemy flask-login werkzeug
```

### 2. Executar o sistema
```bash
python app.py
```

### 3. Acessar no navegador
```
http://localhost:5000
```

### 4. Criar uma conta
- Acesse `/cadastro` e registre-se
- Ou use as credenciais de teste (crie via cadastro)

---

## ✅ Funcionalidades Implementadas

### MVP (Requisitos Funcionais)
- ✅ **RF01** – Autenticação de usuários (cadastro + login com hash seguro)
- ✅ **RF02** – Localização/Maps (Leaflet + OpenStreetMap + geolocalização do browser)
- ✅ **RF03** – Listagem de postos (grade com filtros e busca)
- ✅ **RF04** – Filtro de combustível (gasolina, etanol, diesel)
- ✅ **RF05** – Atualização de preços (histórico de 7 dias por posto)

### Funcionalidades Extras
- ✅ **Comparação de preços** – Tabela + gráfico de barras entre até 5 postos
- ✅ **Alertas de preço** – Notificações quando preço atinge o limite
- ✅ **Classificação/Avaliação** – Sistema de estrelas (1–5) com comentários
- ✅ **Rota até o posto** – Integração com Google Maps
- ✅ **Histórico de preços** – Gráfico dos últimos 7 dias

### Requisitos Não Funcionais
- ✅ **RNF01** – Interface responsiva e intuitiva
- ✅ **RNF02** – Busca ágil por postos com filtros em tempo real
- ✅ **RNF03** – Senhas criptografadas (Werkzeug PBKDF2), conformidade LGPD
- ✅ **RNF04** – Foco em economia e tempo do usuário

---

## 🗂️ Estrutura do Projeto

```
rota_economica/
├── app.py                  # Aplicação principal Flask
├── rota_economica.db       # Banco SQLite (gerado automaticamente)
├── README.md
└── templates/
    ├── base.html           # Layout base com sidebar
    ├── login.html          # Tela de login
    ├── cadastro.html       # Tela de cadastro
    ├── mapa.html           # Mapa interativo com Leaflet
    ├── postos.html         # Listagem de postos
    ├── comparacao.html     # Comparação de preços
    ├── alertas.html        # Alertas de preço
    ├── perfil.html         # Perfil do usuário
    └── suporte.html        # FAQ e suporte
```

---

## 🗄️ Modelagem do Banco de Dados

| Tabela | Campos principais |
|--------|-------------------|
| `usuarios` | id, nome, email, senha_hash, cidade, pais |
| `postos` | id, nome, endereco, bandeira, latitude, longitude, horario |
| `precos` | id, posto_id, tipo, valor, atualizado_em |
| `avaliacoes` | id, posto_id, usuario_id, nota, comentario |
| `alertas_preco` | id, usuario_id, posto_id, tipo, preco_limite, ativo |

---

## 🛠️ Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python + Flask |
| Banco de dados | SQLite (SQLAlchemy ORM) |
| Autenticação | Flask-Login + Werkzeug |
| Interface | HTML5 + CSS3 + JavaScript |
| Mapas | Leaflet.js + OpenStreetMap + CartoDB |
| Fontes | Google Fonts (Syne + DM Sans) |

---

## 📅 Cronograma (Metodologia RAD)

| Ciclo | Semanas | Entregável |
|-------|---------|-----------|
| 1 | 1–2 | Requisitos, protótipo, BD, cadastro, mapa |
| 2 | 3–4 | Comparação, filtros, avaliações |
| 3 | 5–6 | Alertas, testes, polimento, entrega final |
