# Funil de Vendas — Plataforma de IA para Escolas de Idiomas

## Produto

Plataforma com 3 módulos para escolas de idiomas e professores autônomos:
1. **Agente Professor** — tutor de inglês por IA no WhatsApp (pronúncia, conversação, jogos)
2. **Agente SDR** — vendedor automático que capta e qualifica leads no WhatsApp
3. **CRM** — gestão de alunos, pipeline de vendas, métricas (fase 2)

---

## Público-Alvo

### Persona 1: Dono de escola de idiomas (pequena/média)
- **Dor**: Alunos desistem por falta de prática entre as aulas. Concorrência com apps (Duolingo, etc). Dificuldade de captar novos alunos. Depende de indicação.
- **Desejo**: Reter alunos, se diferenciar, escalar sem aumentar custo com professores.
- **Onde está**: Instagram, grupos de WhatsApp de empreendedores, eventos de franquias de educação.
- **Gatilho de compra**: Ver o produto funcionando. Entender que o aluno dele vai praticar TODO DIA, não só na aula.

### Persona 2: Professor autônomo de inglês
- **Dor**: Não consegue atender mais alunos sem trabalhar mais horas. Aluno cancela fácil. Não tem diferencial.
- **Desejo**: Escalar receita sem escalar horas. Dar mais valor ao aluno. Parecer profissional.
- **Onde está**: Instagram, TikTok, comunidades de professores, LinkedIn.
- **Gatilho de compra**: "Com isso eu consigo cobrar mais e o aluno treina sozinho entre as aulas."

---

## Estrutura do Funil

```
[TOPO]  Ad — Anúncios (Instagram/Facebook/TikTok)
         ↓
[MEIO]  Form — Landing page com formulário de captura
         ↓           (nome, WhatsApp, escola, qtd alunos, desafio)
[MEIO]  WhatsApp — SDR recebe dados e inicia conversa personalizada
         ↓              (qualifica, demonstra, aquece)
[FUNDO] Call — SDR agenda, VOCÊ liga para fechar
         ↓
[PÓS]   Ativação — Trial 7 dias + onboarding
         ↓
[PÓS]   Retenção — Acompanhamento + resultados + upgrade
```

### Fluxo técnico: Ad → Form → WhatsApp → Call

1. **Ad**: Leva o lead para a landing page (/)
2. **Form**: Lead preenche formulário na landing page
3. **Backend**: `POST /api/leads` salva no banco (`sdr_leads`) e dispara o SDR automaticamente
4. **SDR**: Envia primeira mensagem no WhatsApp JÁ personalizada com os dados do form
5. **SDR**: Qualifica, manda demos (quiz, exemplo de conversa), tira dúvidas
6. **SDR**: Quando o lead está quente, agenda call → notifica você
7. **Você**: Liga, fecha o trial, faz onboarding

---

## TOPO DO FUNIL — Atração

### Estratégia de Conteúdo (Instagram + TikTok)

#### Pilar 1: Demonstração do Produto (40% dos posts)
Mostrar o agente funcionando. O produto SE VENDE quando as pessoas veem.

**Criativos:**

1. **"Meu aluno praticou inglês às 23h de um domingo"**
   - Formato: Reels/TikTok, 15-30 seg
   - Conteúdo: Tela gravada do WhatsApp mostrando um aluno conversando com o agente. O agente corrige naturalmente, faz perguntas, manda enquete.
   - Hook: "Sabe o que acontece quando seu aluno tem um professor de inglês disponível 24h?"
   - CTA: "Link na bio pra testar grátis"

2. **"O agente corrigiu meu aluno SEM ele perceber"**
   - Formato: Reels, 20 seg
   - Conteúdo: Print da conversa onde o aluno erra ("I goed to the store") e o agente responde naturalmente ("Oh you went to the store? Nice! What did you get?")
   - Texto na tela: "Correção implícita. Sem constrangimento. O aluno aprende SEM saber que errou."
   - CTA: "Imagina isso com TODOS os seus alunos"

3. **"Quiz de inglês no WhatsApp"**
   - Formato: Reels interativo, 15 seg
   - Conteúdo: Mostrar a enquete do WhatsApp aparecendo: "What's the past tense of 'go'?" com opções. O aluno responde. O agente reage.
   - Hook: "Gamificação no WhatsApp. Seus alunos vão PEDIR pra estudar."

4. **"Antes vs Depois: pronúncia do aluno"**
   - Formato: Reels, 30 seg
   - Conteúdo: Áudio do aluno no dia 1 vs dia 30. Mostrar evolução real.
   - Hook: "30 dias praticando com IA. Olha a diferença."

5. **"O avatar 3D que ensina inglês"**
   - Formato: Reels, 15 seg
   - Conteúdo: Gravação da tela do chat web com o avatar falando e movendo a boca.
   - Hook: "Sim, isso é uma IA. E ela ensina inglês melhor que muito app por aí."

#### Pilar 2: Dor do público (30% dos posts)

6. **"Seu aluno só pratica 2h por semana?"**
   - Formato: Carrossel, 5 slides
   - Slide 1: "Seu aluno tem 2h de aula por semana"
   - Slide 2: "São 166 horas SEM praticar"
   - Slide 3: "Ele esquece 80% até a próxima aula"
   - Slide 4: "E se ele pudesse praticar TODO DIA, por 10 min, no WhatsApp?"
   - Slide 5: "Existe uma solução. Link na bio."

7. **"Por que seus alunos desistem em 3 meses"**
   - Formato: Reels com texto na tela
   - Conteúdo: "Não é o preço. Não é o professor. É que eles não PRATICAM entre as aulas. E quando não praticam, não evoluem. E quando não evoluem, desistem."
   - CTA: "E se eu te mostrasse como resolver isso?"

8. **"Duolingo é seu concorrente. Sabia?"**
   - Formato: Reels provocativo
   - Conteúdo: "Seu aluno paga R$300/mês na sua escola. Mas ele também usa Duolingo grátis. Um dia ele pensa: 'pra que pagar se o app é de graça?' A menos que sua escola ofereça algo que o Duolingo NUNCA vai ter: conversação REAL com correção inteligente."

9. **"O professor que trabalha 24h e não reclama"**
   - Formato: Imagem com texto
   - Conteúdo: Humor. "Contratei um professor que trabalha 24h, feriado, domingo, madrugada. Não pede aumento. Não falta. E os alunos AMAM ele."
   - CTA: "Quer conhecer?"

#### Pilar 3: Autoridade + Educação (20% dos posts)

10. **"Como IA está mudando o ensino de idiomas"**
    - Formato: Carrossel educativo, 7 slides
    - Conteúdo: Dados sobre IA na educação, cases, tendências. Posiciona você como especialista.

11. **"3 erros de pronúncia que todo brasileiro comete"**
    - Formato: Reels educativo
    - Conteúdo: TH, vogais curtas, R americano. "E o nosso agente detecta e corrige TODOS eles automaticamente."

12. **"O que é avaliação fonêmica?"**
    - Formato: Carrossel
    - Conteúdo: Explicar como funciona o Azure Speech, o que são fonemas, como a IA avalia. Gera autoridade técnica.

#### Pilar 4: Prova social (10% dos posts)

13. **Depoimentos de escolas usando**
    - Formato: Vídeo/print
    - Conteúdo: (Quando tiver) Prints de donos de escola falando dos resultados.

14. **Números e métricas**
    - Formato: Imagem
    - Conteúdo: "Alunos que usam o agente praticam 5x mais que alunos sem ele." (Dados internos)

---

### Estratégia de Anúncios Pagos

#### Campanha 1: Topo — Awareness (Instagram/Facebook Ads)

**Público:**
- Interesses: escola de idiomas, ensino de inglês, franquias educação, empreendedorismo educação
- Cargo: proprietário, diretor, coordenador pedagógico
- Idade: 28-55
- Lookalike de quem já interagiu

**Criativo A — Vídeo curto (15 seg)**
- Tela do WhatsApp com o agente conversando
- Texto overlay: "Seus alunos praticando inglês TODOS OS DIAS no WhatsApp"
- CTA: "Saiba mais"

**Criativo B — Carrossel de dor**
- Slide 1: "Seus alunos só praticam na aula?"
- Slide 2: "E se eles tivessem um tutor 24h no WhatsApp?"
- Slide 3: "Correção de pronúncia por IA"
- Slide 4: "Jogos e quizzes para engajar"
- Slide 5: "Teste grátis por 7 dias → Link"

**Criativo C — Demonstração direta**
- Gravar o celular mostrando uma conversa real com o agente
- Estilo "POV: seu aluno praticando inglês às 11h da noite"

#### Campanha 2: Meio — Consideração (Retargeting)

**Público:** Quem assistiu 50%+ dos vídeos, visitou o site, clicou no link

**Criativo D — Depoimento/Case**
- Vídeo seu explicando como funciona, resultados possíveis

**Criativo E — Comparativo**
- "Sem o agente: aluno pratica 2h/semana"
- "Com o agente: aluno pratica 2h/semana + 30min/dia no WhatsApp"
- "= 5.5h de prática por semana. 175% a mais."

#### Campanha 3: Fundo — Conversão (Retargeting quente)

**Público:** Quem visitou a landing page, clicou no WhatsApp mas não converteu

**Criativo F — Urgência**
- "Vagas limitadas para o trial gratuito"
- "Já são X escolas usando. Falta a sua."

**Criativo G — Objeção killer**
- "Não, não substitui o professor. POTENCIALIZA o professor."
- "O aluno pratica com a IA e chega na aula PRONTO."

---

## MEIO DO FUNIL — Captura e Qualificação

### Landing Page (estrutura)

```
HEADER:
"Seus alunos praticando inglês TODO DIA no WhatsApp — com IA"
[Vídeo demonstração] [Botão: Testar grátis por 7 dias]

SEÇÃO 1 — O Problema:
"Seus alunos só praticam 2h por semana. Nas outras 166h, eles esquecem."

SEÇÃO 2 — A Solução:
"Um tutor de inglês por IA no WhatsApp dos seus alunos"
- Conversação natural em inglês
- Correção inteligente de pronúncia
- Jogos e quizzes que engajam
- Disponível 24/7
- Personalizado com o conteúdo da SUA escola

SEÇÃO 3 — Como funciona:
3 passos:
1. Você configura o agente com a cara da sua escola
2. Seus alunos adicionam o número no WhatsApp
3. Eles praticam todo dia. Você acompanha o progresso.

SEÇÃO 4 — Módulos:
- Agente Professor (ensina)
- Agente SDR (capta alunos para sua escola)
- Painel de gestão (acompanha tudo)

SEÇÃO 5 — Prova social / Números

SEÇÃO 6 — FAQ

SEÇÃO 7 — CTA Final:
"Comece o trial gratuito agora"
[Botão → Abre WhatsApp do Agente SDR]
```

### Fluxo do Lead

```
Lead clica no botão da landing page
    ↓
Abre WhatsApp com mensagem pré-preenchida
    ↓
Agente SDR recebe e inicia qualificação
    ↓
Coleta: nome, tipo (escola/professor), qtd alunos, momento
    ↓
Demonstra o produto (envia exemplo de conversa, enquete)
    ↓
Oferece trial de 7 dias
    ↓
Se aceita → onboarding (configura agente com materiais da escola)
    ↓
Se hesita → follow-up automático em 24h, 72h, 7 dias
```

---

## FUNDO DO FUNIL — Conversão

### Trial Gratuito (7 dias)

O trial é a arma principal. O dono da escola EXPERIMENTA o agente com seus próprios alunos.

**O que o trial inclui:**
- Agente Professor configurado com nome/personalidade da escola
- Até 10 alunos podem usar
- Todas as funcionalidades (pronúncia, conversação, jogos)
- Painel admin para acompanhar

**O que acontece durante o trial:**
- Dia 1: Onboarding. Configura o agente. Convida 3-5 alunos.
- Dia 3: SDR manda mensagem: "Como está a experiência? Seus alunos já praticaram X vezes."
- Dia 5: SDR envia relatório: "Seus alunos praticaram Y minutos esta semana."
- Dia 7: SDR liga/manda áudio: "O trial acaba hoje. Quer continuar? Tenho uma condição especial."

### Objeções comuns e respostas

| Objeção | Resposta |
|---------|---------|
| "Vai substituir meu professor?" | "Não. Potencializa. O aluno pratica com a IA e chega na aula pronto. Seu professor ganha tempo." |
| "Meus alunos não vão usar" | "O agente puxa conversa. Manda quiz. É como um amigo no WhatsApp. A taxa de engajamento é de X%." |
| "É caro" | "Quanto custa perder 1 aluno por mês? O agente custa menos que 1 mensalidade." |
| "Já uso Duolingo/app" | "App não conversa. Não corrige pronúncia em tempo real. Não personaliza com o conteúdo da sua escola." |
| "Preciso pensar" | "Tudo bem. Posso te enviar um vídeo de 2 min mostrando um aluno real usando? Aí você decide com calma." |

---

## PÓS-VENDA

### Onboarding (primeiros 7 dias após assinatura)
1. Configurar nome e personalidade do agente
2. Upload de materiais da escola (apostilas, vocabulário, temas)
3. Configurar número de WhatsApp
4. Treinar o dono da escola no painel admin
5. Enviar mensagem modelo para os alunos começarem

### Retenção
- Relatório semanal automático para o dono (engajamento, evolução dos alunos)
- Novas funcionalidades comunicadas pelo SDR
- Grupo VIP de donos de escola (comunidade)
- Upsell: mais alunos, mais módulos, Agente SDR para captação

---

## MÉTRICAS DO FUNIL

| Etapa | Métrica | Meta |
|-------|---------|------|
| Topo | Alcance / Impressões | 50k/mês |
| Topo | Cliques no link | 2-3% CTR |
| Meio | Leads no WhatsApp | 500/mês |
| Meio | Qualificados pelo SDR | 40% |
| Fundo | Trials iniciados | 50% dos qualificados |
| Fundo | Conversão trial→pago | 40% |
| Pós | Churn mensal | <5% |

---

## CALENDÁRIO DE CONTEÚDO (Primeira Semana)

| Dia | Formato | Pilar | Tema |
|-----|---------|-------|------|
| Seg | Reels | Demonstração | "Meu aluno praticou às 23h de domingo" |
| Ter | Carrossel | Dor | "Seu aluno só pratica 2h por semana" |
| Qua | Reels | Demonstração | "Quiz de inglês no WhatsApp" |
| Qui | Imagem | Humor/Dor | "O professor que trabalha 24h" |
| Sex | Reels | Demonstração | "O agente corrigiu sem ele perceber" |
| Sáb | Carrossel | Educação | "3 erros de pronúncia de brasileiro" |
| Dom | Reels | Demonstração | "Avatar 3D que ensina inglês" |

---

## PRECIFICAÇÃO (Sugestão)

| Plano | Público | Limite | Preço sugerido |
|-------|---------|--------|----------------|
| Starter | Professor autônomo | Até 30 alunos | R$ 197/mês |
| Pro | Escola pequena | Até 100 alunos | R$ 497/mês |
| Business | Escola média/grande | Até 300 alunos | R$ 997/mês |
| Enterprise | Franquias/redes | Ilimitado | Sob consulta |

**Incluir em todos:**
- Agente Professor completo
- Painel admin
- Suporte por WhatsApp

**Incluir a partir do Pro:**
- Agente SDR para captação
- Relatórios avançados
- Personalização de conteúdo (RAG)

---

## PRÓXIMOS PASSOS

1. [ ] Criar landing page
2. [ ] Configurar Agente SDR
3. [ ] Gravar 7 criativos da primeira semana
4. [ ] Configurar conta de anúncios (Meta Ads)
5. [ ] Criar link do WhatsApp com mensagem pré-preenchida
6. [ ] Definir precificação final
7. [ ] Montar onboarding automatizado
