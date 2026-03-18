# 🎓 English Pronunciation Assistant

Assistente de pronúncia de inglês para brasileiros via WhatsApp, usando Azure Speech Services para análise fonêmica precisa.

## 📋 Funcionalidades

- ✅ Análise de pronúncia com score 0-100
- ✅ Detecção de fonemas por palavra
- ✅ Identificação de erros típicos de brasileiros (TH, vogais, R americano)
- ✅ Feedback humanizado via GPT
- ✅ Sistema de frases para prática
- ✅ Tracking de progresso por sessão
- ✅ Integração WhatsApp via Uazapi

## 🏗️ Arquitetura

```
WhatsApp (Aluno) 
    ↓ envia áudio
Uazapi (webhook)
    ↓ POST /webhook/uazapi
FastAPI
    ├── Baixa áudio via Uazapi
    ├── Converte para WAV (pydub/ffmpeg)
    ├── Azure Pronunciation Assessment
    ├── Analisa erros (foco brasileiros)
    ├── GPT-4.1-mini gera feedback
    └── Responde via Uazapi API
        ↓
WhatsApp (Aluno recebe feedback)
```

## 🚀 Deploy Rápido

### 1. Clonar e configurar

```bash
# Clonar repositório
git clone <seu-repo>
cd english-pronunciation-assistant

# Copiar e editar variáveis de ambiente
cp .env.example .env
nano .env
```

### 2. Preencher variáveis de ambiente

```env
# Uazapi (obrigatório)
UAZAPI_BASE_URL=https://sua-instancia.uazapi.com
UAZAPI_TOKEN=seu-token-aqui

# Azure Speech (obrigatório)
# Criar em: https://portal.azure.com → Create Resource → Speech Services
AZURE_SPEECH_KEY=sua-chave-aqui
AZURE_SPEECH_REGION=eastus

# OpenAI (obrigatório)
OPENAI_API_KEY=sk-...
```

### 3. Deploy com Docker

```bash
docker-compose up -d
```

### 4. Configurar webhook na Uazapi

No painel da Uazapi:
1. Vá em **Webhooks**
2. Adicione novo webhook:
   - **URL**: `https://seu-dominio.com/webhook/uazapi`
   - **Events**: `messages`
   - **Enabled**: true

## 📱 Comandos do Bot

| Comando | Descrição |
|---------|-----------|
| `/start` ou `/help` | Mostra mensagem de boas-vindas |
| `/phrase` | Recebe uma nova frase para praticar |
| `/phrase th_sounds` | Frase focada em sons de TH |
| `/phrase vowels` | Frase focada em vogais |
| `/phrase r_sound` | Frase focada no R americano |
| `/progress` | Mostra progresso da sessão atual |
| `/level beginner` | Define nível iniciante |
| `/level intermediate` | Define nível intermediário |
| `/level advanced` | Define nível avançado |

## 🔧 Configuração Azure Speech

### Criar recurso no Azure:

1. Acesse [Azure Portal](https://portal.azure.com)
2. **Create a resource** → **Speech Services**
3. Preencha:
   - **Subscription**: Sua assinatura
   - **Resource group**: Criar novo ou usar existente
   - **Region**: `East US` (recomendado)
   - **Name**: `pronunciation-assistant`
   - **Pricing tier**: `Free F0` (5 horas/mês) ou `Standard S0`
4. Após criar, vá em **Keys and Endpoint**
5. Copie **KEY 1** para `AZURE_SPEECH_KEY`

### Preços Azure Speech:

| Tier | Limite | Custo |
|------|--------|-------|
| Free F0 | 5 horas/mês | Grátis |
| Standard S0 | Ilimitado | ~$1/hora de áudio |

## 📊 Fonemas Analisados

O sistema identifica erros típicos de brasileiros:

| Fonema | Som | Exemplo | Erro Comum |
|--------|-----|---------|------------|
| θ | TH surdo | think | T ou F |
| ð | TH sonoro | this | D ou Z |
| æ | A aberto | cat | É ou A fechado |
| ɪ | I curto | bit | I longo |
| ʊ | U curto | put | U longo |
| ɹ | R americano | car | R brasileiro |
| ŋ | NG final | sing | N + G |

## 🧪 Testando Localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar servidor
uvicorn app.main:app --reload --port 8000

# Testar health check
curl http://localhost:8000/health
```

Para testar com WhatsApp local, use ngrok:

```bash
ngrok http 8000
# Copie a URL https://xxx.ngrok.io e configure na Uazapi
```

## 📁 Estrutura do Projeto

```
english-pronunciation-assistant/
├── app/
│   ├── __init__.py
│   ├── config.py              # Configurações (Pydantic Settings)
│   ├── models.py              # Modelos de dados
│   ├── main.py                # FastAPI app + webhook
│   └── services/
│       ├── __init__.py
│       ├── uazapi.py          # Integração Uazapi
│       ├── azure_speech.py    # Azure Pronunciation Assessment
│       ├── error_analyzer.py  # Análise de erros de brasileiros
│       ├── feedback_generator.py  # Geração de feedback via GPT
│       └── session_manager.py # Gerenciamento de sessões
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🔄 Fluxo de Dados

```
1. Aluno envia /phrase
   └── Bot responde com frase: "I think that this is great"

2. Aluno grava áudio pronunciando a frase
   └── Webhook recebe mensagem de áudio

3. Sistema processa:
   ├── Baixa áudio via Uazapi API
   ├── Converte OGG → WAV (16kHz mono)
   ├── Envia para Azure Pronunciation Assessment
   ├── Recebe scores por palavra e fonema
   ├── Identifica erros de brasileiro
   └── GPT gera feedback humanizado

4. Aluno recebe feedback:
   └── "🌟 Score: 72/100
        Muito bem! Seu TH em 'think' ficou ótimo!
        Dica: Em 'this', lembre de vibrar o TH..."
```

## 🛡️ Segurança

- Variáveis sensíveis via `.env` (não commitadas)
- Webhook processa em background (não expõe erros)
- Logs não incluem conteúdo de mensagens
- Health check para monitoramento

## 📈 Melhorias Futuras

- [ ] Persistência em Redis/Supabase
- [ ] Áudio de exemplo via ElevenLabs
- [ ] Dashboard de progresso do aluno
- [ ] Gamificação (badges, streaks)
- [ ] Múltiplos idiomas de feedback

## 📄 Licença

MIT
