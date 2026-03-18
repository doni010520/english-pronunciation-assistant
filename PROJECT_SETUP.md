# English Pronunciation Assistant

## Arquitetura

```
WhatsApp (Aluno) 
    ↓ envia áudio
Uazapi (webhook)
    ↓ POST /webhook/uazapi
FastAPI
    ├── Baixa áudio via Uazapi
    ├── Converte para WAV (Azure requer)
    ├── Azure Pronunciation Assessment
    ├── Analisa erros (foco brasileiros)
    ├── GPT-4.1-mini gera feedback
    └── Responde via Uazapi API
        ↓
WhatsApp (Aluno recebe feedback)
```

## Fluxo Detalhado

1. Aluno recebe frase para praticar: "I thought about that thing"
2. Aluno grava áudio no WhatsApp
3. Uazapi envia webhook para nosso servidor
4. Baixamos o áudio, convertemos para WAV
5. Azure analisa pronúncia (score por fonema)
6. Identificamos erros típicos de brasileiros
7. GPT gera feedback pedagógico humanizado
8. Enviamos resposta pelo WhatsApp

## Configuração Uazapi

No painel da Uazapi, configure o webhook:
- URL: `https://seu-dominio.com/webhook/uazapi`
- Events: `messages`
- Método: POST

## Variáveis de Ambiente Necessárias

```
UAZAPI_BASE_URL=https://sua-instancia-uazapi.com
UAZAPI_TOKEN=seu-token-aqui
AZURE_SPEECH_KEY=sua-chave-azure
AZURE_SPEECH_REGION=eastus
OPENAI_API_KEY=sua-chave-openai
```
