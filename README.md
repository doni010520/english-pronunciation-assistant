# Plataforma de IA para Escolas de Idiomas

Plataforma SaaS white-label com 3 modulos para escolas de idiomas e professores autonomos de ingles no Brasil.

## Produto

| Modulo | Funcao | Status |
|--------|--------|--------|
| **Agente Professor** | Tutor de ingles por IA no WhatsApp (pronuncia, conversacao, jogos) | Pronto |
| **Agente SDR** | Vendedor automatico que qualifica leads no WhatsApp | Pronto |
| **CRM** | Gestao de alunos, pipeline de vendas, metricas | Planejado |

Cada cliente (escola) recebe seu proprio agente personalizado com nome, personalidade e conteudo da escola.

---

## Arquitetura

```
                          +-----------------+
                          |   Landing Page  |
                          |   /landing      |
                          +--------+--------+
                                   |
                          +--------v--------+
                          |   Formulario    |
  Meta Ads  ----------->  |   / (form.html) |
                          +--------+--------+
                                   |
                          POST /api/leads
                                   |
              +--------------------+--------------------+
              |                                         |
   +----------v----------+               +--------------v-----------+
   |   Banco (Supabase)  |               |   Agente SDR             |
   |   sdr_leads          |               |   WhatsApp (Uazapi #2)  |
   |   sdr_demo_calls     |               |   Qualifica + agenda    |
   |   sdr_followups      |               |   demo call             |
   +---------------------+               +--------------------------+
                                                     |
                                              Voce liga e fecha
                                                     |
                                          +----------v-----------+
                                          |   Agente Professor   |
                                          |   WhatsApp (Uazapi #1)|
                                          |   Ensina alunos      |
                                          +----------+-----------+
                                                     |
                                +--------------------+--------------------+
                                |                    |                    |
                         +------v------+   +---------v--------+  +-------v--------+
                         | Azure Speech|   | OpenAI GPT/TTS   |  | Supabase DB    |
                         | Pronuncia   |   | Whisper/Embeddings|  | Historico/RAG  |
                         +-------------+   +------------------+  +----------------+
```

### Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + Uvicorn (Python async) |
| Database | Supabase (PostgreSQL + pgvector) |
| Cache | Redis (debounce de mensagens) |
| Speech | Azure Speech Services (avaliacao fonemica) |
| IA | OpenAI GPT-4.1-mini, Whisper, TTS, Embeddings |
| WhatsApp | Uazapi v2 (2 instancias: professor + SDR) |
| Frontend | HTML/CSS/JS + Three.js (avatar 3D) |
| Deploy | Docker + Docker Compose |

---

## Agente Professor

Tutor de ingles que conversa naturalmente com alunos via WhatsApp.

### Filosofia
- **Conversa primeiro, ensino depois.** O agente e um parceiro de conversa, nao um professor chato.
- **Correcao invisivel.** Usa a tecnica "echo correction": repete a forma correta na resposta sem apontar o erro.
- **Gamificacao.** Envia quizzes interativos (enquetes do WhatsApp) para engajar.

### Funcionalidades

- Conversacao natural em ingles/portugues (adapta ao idioma do aluno)
- Avaliacao de pronuncia em tempo real via Azure Speech (9 fonemas problematicos de brasileiros)
- Quizzes e jogos via enquetes do WhatsApp (`POST /send/menu` tipo `poll`)
- Frases de pratica com foco em fonemas especificos
- Tracking de progresso por aluno
- Base de conhecimento RAG (upload de materiais da escola)
- Avatar 3D com lipsync no chat web (`/chat`)
- Painel admin para configuracao (`/admin`)

### Fonemas Analisados

| Fonema | Som | Exemplo | Erro Comum do Brasileiro |
|--------|-----|---------|--------------------------|
| θ | TH surdo | think | T ou F |
| ð | TH sonoro | this | D ou Z |
| æ | A aberto | cat | E ou A fechado |
| ɪ | I curto | bit | I longo |
| ʊ | U curto | put | U longo |
| ʌ | Schwa | cup | A aberto |
| ɹ | R americano | car | R brasileiro |
| ŋ | NG final | sing | N + G |
| l | L final | call | U |

### Tools do Agente (function calling)

| Tool | Descricao |
|------|-----------|
| `give_practice_phrase` | Gera frase para praticar pronuncia |
| `show_progress` | Mostra estatisticas do aluno |
| `set_level` | Altera nivel (beginner/intermediate/advanced) |
| `set_focus` | Altera foco fonetico (th_sounds/vowels/r_sound) |
| `send_quiz` | Envia enquete interativa no WhatsApp |

---

## Agente SDR

Vendedor automatico que qualifica leads e agenda demonstracoes via WhatsApp.

### Fluxo

1. Lead preenche formulario no site (vindo de anuncio)
2. `POST /api/leads` salva no banco e dispara o SDR automaticamente
3. SDR envia primeira mensagem no WhatsApp ja personalizada com os dados do form
4. SDR qualifica, manda demos (quiz, exemplo de conversa), tira duvidas
5. SDR agenda demo call com o lead
6. Voce liga, faz demo ao vivo e fecha

### Tools do SDR (function calling)

| Tool | Descricao |
|------|-----------|
| `qualify_lead` | Salva/atualiza dados do lead |
| `send_demo` | Envia demonstracao (quiz, conversa exemplo, pronuncia) |
| `schedule_demo_call` | Agenda ligacao de demonstracao |
| `send_pricing` | Envia tabela de precos |
| `set_followup` | Agenda follow-up automatico |

### Pipeline de Leads

`new` → `qualifying` → `interested` → `demo_scheduled` → `closed_won` / `closed_lost`

---

## Funil de Vendas

Estrategia completa documentada em `docs/FUNIL_DE_VENDAS.md`.

### Estrutura: Ad → Form → WhatsApp → Call

```
[TOPO]  Ad (Instagram/Facebook/TikTok)
         ↓
[MEIO]  Formulario de captura (/ no site)
         ↓  nome, WhatsApp, tipo, escola, qtd alunos, desafio
[MEIO]  WhatsApp — SDR qualifica e aquece
         ↓
[FUNDO] Call — voce faz demo ao vivo e fecha
         ↓
[POS]   Onboarding + acompanhamento
```

### Publico-Alvo

| Persona | Dor | Pitch |
|---------|-----|-------|
| Dono de escola | Alunos desistem, concorrencia com IA/apps | "Seus alunos praticam todo dia. Retencao sobe." |
| Professor autonomo | Nao escala sem trabalhar mais | "Escale sem contratar. Aluno treina sozinho." |

### Precificacao Sugerida

| Plano | Publico | Limite | Preco |
|-------|---------|--------|-------|
| Starter | Professor autonomo | 30 alunos | R$ 197/mes |
| Pro | Escola pequena | 100 alunos | R$ 497/mes |
| Business | Escola media/grande | 300 alunos | R$ 997/mes |
| Enterprise | Franquias/redes | Ilimitado | Sob consulta |

### Criativos (prontos em `app/static/criativos/`)

| Arquivo | Tipo | Angulo |
|---------|------|--------|
| `carrossel-2h-por-semana.html` | Carrossel 5 slides | Dor: retencao |
| `carrossel-3-erros-pronuncia.html` | Carrossel 5 slides | Educativo |
| `imagem-chatgpt-ameaca.html` | Imagem unica | Medo: IA como ameaca |
| `imagem-correcao-invisivel.html` | Imagem unica | Demo do produto |
| `imagem-professor-24h.html` | Imagem unica | Humor |

Abrir cada HTML no navegador e fazer screenshot (1080x1080) para postar no Instagram.

---

## Paginas

| Rota | Pagina | Descricao |
|------|--------|-----------|
| `/` | Formulario | Typeform-style, captura leads dos anuncios |
| `/landing` | Landing page | Pagina completa com todas as secoes |
| `/chat` | Chat web | Avatar 3D com lipsync + conversa |
| `/admin` | Painel admin | Configuracoes, documentos RAG, usuarios |

---

## Deploy

### 1. Clonar e configurar

```bash
git clone <seu-repo>
cd english-pronunciation-assistant
cp .env.example .env
```

### 2. Variaveis de ambiente

```env
# Uazapi - Agente Professor
UAZAPI_BASE_URL=https://instancia-professor.uazapi.com
UAZAPI_TOKEN=token-professor

# Uazapi - Agente SDR (numero separado)
UAZAPI_SDR_BASE_URL=https://instancia-sdr.uazapi.com
UAZAPI_SDR_TOKEN=token-sdr

# Azure Speech
AZURE_SPEECH_KEY=sua-chave
AZURE_SPEECH_REGION=eastus

# OpenAI
OPENAI_API_KEY=sk-...

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...

# Redis
REDIS_URL=redis://localhost:6379

# Admin
ADMIN_TOKEN=seu-token-admin
```

### 3. Banco de dados

Rodar as migrations no Supabase (SQL Editor):

```
supabase/migrations/001_initial_schema.sql       — tabelas base (users, sessions, agent_settings)
supabase/migrations/002_conversational_agent.sql  — historico de conversa, RAG
supabase/migrations/003_sdr_agent.sql             — leads, demo calls, followups
```

### 4. Docker

```bash
docker-compose up -d
```

### 5. Webhooks

Configurar na Uazapi de cada instancia:

| Instancia | Webhook URL |
|-----------|-------------|
| Professor | `https://seudominio.com/webhook/uazapi` |
| SDR | `https://seudominio.com/webhook/sdr` |

### 6. Testar localmente

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Com ngrok para webhook
ngrok http 8000
```

---

## Estrutura do Projeto

```
english-pronunciation-assistant/
├── app/
│   ├── __init__.py
│   ├── config.py                    # Configuracoes (Pydantic Settings)
│   ├── models.py                    # Modelos de dados
│   ├── main.py                      # FastAPI app + webhooks + endpoints
│   ├── static/
│   │   ├── form.html                # Formulario de captura (typeform-style)
│   │   ├── landing.html             # Landing page completa
│   │   ├── chat.html                # Chat web com avatar 3D
│   │   ├── admin.html               # Painel admin
│   │   └── criativos/               # Criativos para Instagram/ads
│   │       ├── carrossel-2h-por-semana.html
│   │       ├── carrossel-3-erros-pronuncia.html
│   │       ├── imagem-chatgpt-ameaca.html
│   │       ├── imagem-correcao-invisivel.html
│   │       └── imagem-professor-24h.html
│   └── services/
│       ├── __init__.py
│       ├── agent.py                 # Agente Professor (prompt + tools)
│       ├── sdr_agent.py             # Agente SDR (prompt + tools)
│       ├── uazapi.py                # Integracao Uazapi (texto, audio, poll)
│       ├── azure_speech.py          # Azure Pronunciation Assessment
│       ├── error_analyzer.py        # Analise de erros de brasileiros
│       ├── feedback_generator.py    # Geracao de feedback + TTS + vision
│       ├── session_manager.py       # Gerenciamento de sessoes
│       └── rag.py                   # RAG (knowledge base + embeddings)
├── supabase/
│   └── migrations/
│       ├── 001_initial_schema.sql
│       ├── 002_conversational_agent.sql
│       └── 003_sdr_agent.sql
├── docs/
│   └── FUNIL_DE_VENDAS.md          # Estrategia completa do funil
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Banco de Dados

### Tabelas do Professor

| Tabela | Descricao |
|--------|-----------|
| `users` | Sessao atual + preferencias do aluno |
| `session_history` | Scores historicos de pronuncia |
| `conversation_history` | Historico de conversa aluno-agente |
| `agent_settings` | Config do agente (nome, personalidade, prompt) |
| `knowledge_documents` | Metadados de documentos RAG |
| `knowledge_chunks` | Chunks com embeddings (1536-dim, pgvector) |

### Tabelas do SDR

| Tabela | Descricao |
|--------|-----------|
| `sdr_leads` | Pipeline de leads (phone PK) |
| `sdr_conversation_history` | Historico de conversa lead-SDR |
| `sdr_demo_calls` | Demo calls agendadas |
| `sdr_followups` | Follow-ups automaticos |

---

## API Endpoints

### Webhooks

| Metodo | Rota | Descricao |
|--------|------|-----------|
| POST | `/webhook/uazapi` | Webhook do WhatsApp do Professor |
| POST | `/webhook/sdr` | Webhook do WhatsApp do SDR |

### Publicos

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/` | Formulario de captura de leads |
| GET | `/landing` | Landing page |
| GET | `/chat` | Chat web com avatar |
| POST | `/api/leads` | Recebe dados do form e dispara SDR |
| POST | `/api/chat` | Endpoint do chat web |
| GET | `/health` | Health check |

### Admin (requer Authorization header)

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/admin` | Painel admin |
| GET | `/api/admin/settings` | Buscar configuracoes |
| POST | `/api/admin/settings` | Salvar configuracoes |
| GET | `/api/admin/documents` | Listar documentos RAG |
| POST | `/api/admin/documents` | Upload documento RAG |
| DELETE | `/api/admin/documents/{id}` | Deletar documento |
| GET | `/api/admin/users` | Listar alunos |
| GET | `/api/sdr/leads` | Listar leads do SDR |

---

## Checklist para ir ao ar

- [ ] Configurar instancia Uazapi para o Professor (numero de WhatsApp dos alunos)
- [ ] Configurar instancia Uazapi para o SDR (numero de WhatsApp de vendas)
- [ ] Rodar as 3 migrations no Supabase
- [ ] Preencher `.env` com todas as chaves
- [ ] Deploy (Docker ou servidor)
- [ ] Configurar webhooks nas 2 instancias Uazapi
- [ ] Trocar link do WhatsApp no formulario (form.html)
- [ ] Comprar dominio e apontar para o servidor
- [ ] Criar conta Instagram do produto
- [ ] Gravar/postar os primeiros criativos
- [ ] Configurar Meta Ads (Business Manager + pixel)
- [ ] Lancar primeira campanha (R$ 30-50/dia)
- [ ] Monitorar leads no `/api/sdr/leads`

---

## Licenca

MIT
