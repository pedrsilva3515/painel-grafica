# Painel Gráfica — Especificação do Projeto

## Visão Geral

App desktop Windows em PyQt6 para controle operacional de uma gráfica de produção rápida. Roda em background como ícone na bandeja do sistema, é acionado por hotkey global, e centraliza buscas, kanban de pedidos, alertas de prazo, lembretes e cálculos — tudo sem sair do fluxo de trabalho.

**Problema que resolve:** informação fragmentada entre pastas, Mubisys (OS), Mobichat (WhatsApp), e lembretes mentais. O painel unifica tudo numa interface acionável de qualquer lugar do Windows.

---

## Stack Técnica

| Componente | Tecnologia |
|---|---|
| UI principal | PyQt6 |
| Hotkey global | `keyboard` lib |
| Banco local | SQLite via `sqlite3` |
| Notificações nativas | `QSystemTrayIcon` + `win10toast` |
| Startup automático | Registro do Windows (via `winreg`) |
| Hash de senha | `bcrypt` |
| Busca de arquivos | `os.walk` + indexação SQLite |
| Integração Todoist | API REST (`requests`) |
| Preview PDF | `PyMuPDF` (`fitz`) — renderiza primeira página como imagem |
| Preview imagens | `QPixmap` nativo do PyQt6 |
| Orçamento (webview) | `PyQt6-WebEngine` (`QWebEngineView` + `QWebChannel`) |
| Configurações | JSON local (`config/settings.json`) |

---

## Arquitetura de Pastas

```
painel-grafica/
├── SPEC.md                    ← este arquivo
├── main.py                    ← entry point: auth → tray → hotkey
├── requirements.txt
├── config/
│   ├── settings.json          ← pastas monitoradas, hotkey, preferências
│   └── auth.json              ← hash bcrypt da senha
├── core/
│   ├── auth.py                ← login, hash, sessão
│   ├── hotkey.py              ← registro do atalho global
│   ├── tray.py                ← ícone bandeja + menu de contexto
│   └── startup.py             ← registro no boot do Windows
├── modules/
│   ├── command_palette/
│   │   ├── palette.py         ← janela flutuante principal
│   │   └── actions/
│   │       ├── file_search.py ← busca em pastas configuradas
│   │       ├── client_search.py ← busca por nome de cliente no banco
│   │       ├── calculator.py  ← cálculos com templates estruturados
│   │       └── mubisys.py     ← abrir OS no Mubisys via URL/browser
│   ├── kanban/
│   │   ├── board.py           ← widget kanban PyQt6
│   │   ├── todoist_sync.py    ← sync bidirecional com Todoist API
│   │   └── alerts.py          ← detectar pedidos parados > N dias
│   ├── deadlines/
│   │   ├── monitor.py         ← varrer pastas por data de arquivo/metadado
│   │   └── scanner.py         ← classificar: ok / próximo / vencido
│   ├── reminders/
│   │   └── manager.py         ← lembretes com QTimer + notificações
│   ├── daily_panel/           ← FASE 2: janela automática diária
│   │   ├── panel.py           ← janela de resumo diário
│   │   └── scheduler.py       ← QTimer que aciona às 8h
│   ├── preview/               ← FASE 2: thumbnail no Command Palette
│   │   ├── renderer.py        ← PNG/JPG via QPixmap, PDF via PyMuPDF
│   │   └── cache.py           ← cache de thumbnails em disco
│   └── quote/                 ← FASE 3: calculadora de orçamento
│       ├── panel.py           ← QWebEngineView carregando o HTML existente
│       └── bridge.py          ← QWebChannel: Python ↔ JS
├── ui/
│   ├── main_window.py         ← janela principal (kanban + painel)
│   ├── login_screen.py        ← tela de senha ao iniciar
│   ├── palette_widget.py      ← command palette (janela flutuante)
│   ├── kanban_widget.py       ← board visual de pedidos
│   ├── daily_panel_widget.py  ← UI do painel diário
│   ├── deadlines_widget.py    ← lista de prazos com status visual
│   └── styles/
│       └── theme.qss          ← Qt Style Sheets (dark mode)
└── data/
    ├── db.py                  ← funções SQLite (init, queries)
    ├── grafica.db             ← banco local (clientes, pedidos, lembretes)
    └── assets/
        └── quote_tool/        ← HTML/CSS/JS do quoting tool existente (copiar aqui)
```

---

## Módulos Detalhados

### 1. Infraestrutura Core

**Auth (`core/auth.py`)**
- Tela de senha ao iniciar o app
- Senha armazenada como hash bcrypt em `config/auth.json`
- Sessão liberada por X horas (configurável)
- Troca de senha via menu da bandeja

**Hotkey Global (`core/hotkey.py`)**
- Atalho padrão: `Ctrl+Space` (configurável)
- Funciona mesmo com outra janela em foco
- Abre/fecha o Command Palette
- Usa lib `keyboard` + integração com Qt via `QThread`

**Bandeja do Sistema (`core/tray.py`)**
- Ícone permanente na bandeja do Windows
- Menu de contexto: Abrir painel | Kanban | Prazos | Configurações | Sair
- Exibe notificações nativas de prazo e alertas
- Cor do ícone muda conforme status (ok / atenção / crítico)

**Inicialização (`core/startup.py`)**
- Registra o executável no `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
- Opção de ativar/desativar pelo menu da bandeja
- Inicia minimizado na bandeja (sem janela visível)

---

### 2. Command Palette

**Comportamento:**
- Janela sem borda, centralizada, sempre no topo (`FramelessWindowHint + WindowStaysOnTopHint`)
- Campo de busca + lista de resultados
- Fecha ao pressionar `Esc` ou clicar fora
- Busca em tempo real (debounce de 150ms)

**Tipos de resultado e ações:**

| Prefixo | Ação | Exemplo |
|---|---|---|
| *(sem prefixo)* | Busca arquivo por nome | `logo cliente abc` |
| `@` | Busca cliente no banco | `@maria confecções` |
| `=` | Cálculo estruturado | `=m2 100x50cm 3un` |
| `os:` | Abre OS no Mubisys | `os:1042` |
| `!` | Cria lembrete rápido | `!ligar fornecedor 14h` |

**Busca de arquivos:**
- Pastas monitoradas definidas em `settings.json` (ex: `\\servidor\arte-final\`, `\\servidor\clientes\`)
- Índice SQLite atualizado em background a cada 15 minutos
- Resultado mostra: nome do arquivo, pasta, data de modificação
- `Enter` abre com programa padrão; `Ctrl+Enter` abre a pasta no Explorer

**Calculadora estruturada:**
- Templates definidos pelo usuário em `settings.json`
- Exemplo de template `m2`:
  ```json
  { "nome": "Área m²", "formula": "(largura * altura) / 10000 * quantidade", "unidades": "cm", "output": "{resultado} m² — {quantidade} peças" }
  ```
- Resultado copiado para clipboard automaticamente

---

### 3. Kanban

**Colunas padrão (configuráveis):**
`Entrada → Arte Final → Aguardando Aprovação → Produção → Acabamento → Pronto → Entregue`

**Integração Todoist:**
- Cada coluna = projeto ou label no Todoist
- Sync a cada 5 minutos via API REST
- Movimentação de card no painel → atualiza Todoist automaticamente
- Metadados do pedido (prazo, cliente, valor) guardados nas descrições das tarefas

**Alertas automáticos:**
- Card parado em mesma coluna por mais de N horas → destaque visual + notificação
- Threshold configurável por coluna (ex: "Arte Final" alerta em 4h, "Produção" em 8h)
- Resumo diário às 8h: pedidos do dia, atrasados, para entregar

**Visual:**
- Cards com cor por status de prazo: verde (ok) / amarelo (próximo) / vermelho (vencido)
- Scroll horizontal nas colunas
- Clique duplo abre detalhes do pedido

---

### 4. Monitor de Prazos

**Fontes de dados:**
- Metadados de arquivos em pastas monitoradas (data de criação / modificação)
- Campo de prazo nos cards do kanban
- Lembretes manuais com data

**Classificação:**
- Verde: prazo > 48h
- Amarelo: prazo entre 24h e 48h → notificação na bandeja
- Vermelho: prazo < 24h ou vencido → notificação urgente + destaque no ícone da bandeja

**Varredura:**
- Roda a cada 30 minutos em background (`QTimer`)
- Pode ser acionada manualmente pelo menu da bandeja

---

### 5. Lembretes & Alertas

**Lembretes:**
- Criados via Command Palette (`!texto horário`) ou pelo painel
- Armazenados no SQLite local
- Notificação nativa no horário definido
- Recorrentes: diário, semanal, dia da semana

**Alertas de pedido parado:**
- Cruza dados do kanban com timestamp da última movimentação
- Dispara notificação com nome do pedido e tempo parado
- Pode snooze por X horas diretamente na notificação

---

### 6. Preview de Arquivos

**Onde aparece:** painel lateral direito do Command Palette quando um arquivo de imagem ou PDF está selecionado na lista de resultados.

**Tipos suportados:**

| Formato | Renderização | Lib |
|---|---|---|
| PNG, JPG, JPEG, BMP, WEBP | `QPixmap.fromImage()` | PyQt6 nativo |
| PDF | Primeira página via `fitz.open()` → `page.get_pixmap()` | `PyMuPDF` |
| CDR, AI, outros | Ícone genérico por extensão | nenhuma lib extra |

**Comportamento:**
- Preview aparece automaticamente ao navegar pelos resultados (seta ↓↑)
- Thumbnail máximo: 280×280px, mantendo proporção
- Carregamento em `QThread` separado — não trava a busca
- Cache em memória (últimos 50 thumbnails) via `modules/preview/cache.py`
- Abaixo do thumbnail: nome, extensão, tamanho, data de modificação

**Layout do Command Palette com preview ativo:**
```
┌─────────────────────────────────────────────┐
│ 🔍 logo cliente abc                          │
├───────────────────────┬─────────────────────┤
│ logo_abc_final.png    │                     │
│ logo_abc_v2.pdf       │   [thumbnail]       │
│ banner_abc.jpg        │                     │
│                       │  logo_abc_final.png │
│                       │  PNG · 2.4 MB       │
│                       │  12/05/2025         │
└───────────────────────┴─────────────────────┘
```

**Configurável em `settings.json`:**
```json
"preview": {
  "enabled": true,
  "max_size_mb": 50,
  "show_for_extensions": ["png", "jpg", "jpeg", "pdf", "bmp"]
}
```

---

### 7. Painel Diário

**Propósito:** janela de briefing matinal que consolida tudo que precisa de atenção no dia, sem precisar abrir nenhum outro sistema.

**Acionamento:**
- Automático às 8h (configurável) via `QTimer` checando hora atual a cada minuto
- Manual: clique em "Painel do Dia" no menu da bandeja
- Pode ser desativado por dia ("Não mostrar hoje") ou permanentemente nas configurações

**Seções da janela:**

```
┌──────────────────────────────────────────────┐
│  Bom dia, Pedro · Segunda, 12 de maio        │
├──────────────────────────────────────────────┤
│  🔴 PRAZOS CRÍTICOS (< 24h)                  │
│  · Banner Loja X — vence hoje 17h            │
│  · Adesivo Y — VENCIDO ontem                 │
├──────────────────────────────────────────────┤
│  🟡 PRAZOS PRÓXIMOS (24–48h)                 │
│  · Faixa Z — amanhã 12h                      │
├──────────────────────────────────────────────┤
│  📋 PEDIDOS PARA ENTREGAR HOJE               │
│  · OS 1041 — Cliente A · Pronto              │
│  · OS 1038 — Cliente B · Acabamento          │
├──────────────────────────────────────────────┤
│  ⚠️ PARADOS SEM MOVIMENTAÇÃO                 │
│  · OS 1035 — Arte Final há 2 dias            │
├──────────────────────────────────────────────┤
│  📌 LEMBRETES DE HOJE                        │
│  · Ligar fornecedor de vinil 9h              │
│  · Confirmar instalação Cliente C 14h        │
├──────────────────────────────────────────────┤
│              [Fechar]  [Snooze 1h]           │
└──────────────────────────────────────────────┘
```

**Fontes de dados:**
- Prazos críticos/próximos: `modules/deadlines`
- Pedidos para entregar: cards do kanban com prazo = hoje
- Parados: `modules/kanban/alerts.py`
- Lembretes: `modules/reminders`

**Comportamento técnico:**
- `modules/daily_panel/scheduler.py` roda em `QThread`, checa hora a cada 60s
- Ao disparar, agrega dados das outras fontes e abre `DailyPanelWindow`
- Janela sempre no topo, centralizada, sem barra de título
- Fecha sozinha após 30 minutos se não interagido (configurável)
- "Snooze 1h" agenda nova abertura em 1 hora

---

### 8. Orçamento Rápido

**Abordagem técnica:** em vez de reescrever o quoting tool em Python, ele é carregado via `QWebEngineView` dentro de uma janela PyQt6. Isso preserva toda a lógica JS existente e permite evoluir o HTML independentemente do app.

**Acionamento:**
- Command Palette: digitar `orc:` abre a janela de orçamento
- Menu da bandeja: "Orçamento rápido"
- Atalho secundário configurável (ex: `Ctrl+Shift+O`)

**Arquitetura `QWebEngineView` + `QWebChannel`:**

```
┌─────────────────────────────────────┐
│  PyQt6 Window                        │
│  ┌───────────────────────────────┐  │
│  │  QWebEngineView               │  │
│  │  (carrega quote_tool/index.html) │  │
│  │                               │  │
│  │  JS: window.pyBridge.saveQuote() │  │
│  └──────────────┬────────────────┘  │
│                 │ QWebChannel        │
│  ┌──────────────▼────────────────┐  │
│  │  bridge.py (QObject)          │  │
│  │  def save_quote(self, data):  │  │
│  │      → salva no SQLite        │  │
│  │      → copia para clipboard   │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**O que o `bridge.py` expõe ao JS:**
```python
@pyqtSlot(str)
def save_quote(self, json_data):
    # Salva orçamento no SQLite com timestamp e cliente

@pyqtSlot(str)
def copy_to_clipboard(self, text):
    # Copia resultado para área de transferência

@pyqtSlot(result=str)
def get_client_list(self):
    # Retorna lista de clientes do banco local como JSON
```

**Preparação do HTML existente:**
1. Copiar o `quoting_tool.html` para `data/assets/quote_tool/index.html`
2. Adicionar ao HTML o script de inicialização do `QWebChannel`:
   ```html
   <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
   <script>
   new QWebChannel(qt.webChannelTransport, function(channel) {
       window.pyBridge = channel.objects.bridge;
   });
   </script>
   ```
3. O HTML pode continuar sendo editado normalmente — o app apenas o carrega

**Passos para implementar:**
1. `pip install PyQt6-WebEngine`
2. Criar `modules/quote/bridge.py` com a classe `QuoteBridge(QObject)`
3. Criar `modules/quote/panel.py` com a janela `QWebEngineView`
4. Copiar o HTML do quoting tool para `data/assets/quote_tool/`

---

## Sugestões para Fases Futuras

Além do escopo atual, considere incorporar:

**Lookup de clientes** — banco SQLite com nome, WhatsApp, histórico de pedidos. Acionado via `@nome` no Command Palette. Permite ver últimos pedidos e copiar WhatsApp em um clique.

**Integração Mubisys avançada** — evoluir além de abrir URL: web scraping leve com `requests` + `BeautifulSoup` para puxar status da OS sem abrir o browser.

**Envio rápido WhatsApp** — integração com Evolution API para disparar mensagem de status ao cliente sem sair do painel. Ex: botão "Avisar pronto" no card do kanban.

---

## Fases de Desenvolvimento

### Fase 1 — MVP funcional
**Meta:** app roda, autentica, fica na bandeja, e abre Command Palette com busca de arquivos.

- [ ] Estrutura de pastas criada
- [ ] `main.py`: init → tela de login → bandeja
- [ ] `core/auth.py`: tela de senha com bcrypt
- [ ] `core/tray.py`: ícone bandeja + menu básico
- [ ] `core/hotkey.py`: Ctrl+Space abre Command Palette
- [ ] `core/startup.py`: registro no boot Windows
- [ ] `modules/command_palette/palette.py`: janela flutuante + campo de busca
- [ ] `modules/command_palette/actions/file_search.py`: busca em pastas
- [ ] `data/db.py`: init do banco SQLite
- [ ] `ui/styles/theme.qss`: dark mode base
- [ ] `config/settings.json`: pastas monitoradas, hotkey

### Fase 2 — Kanban + Prazos + Preview + Painel Diário
**Meta:** gerenciamento de pedidos visível, alertas funcionando, preview de arquivos e briefing matinal.

- [ ] `modules/kanban/board.py`: widget kanban
- [ ] `modules/kanban/todoist_sync.py`: sync com Todoist API
- [ ] `modules/kanban/alerts.py`: pedidos parados
- [ ] `modules/deadlines/monitor.py`: varredura de prazos
- [ ] `modules/deadlines/scanner.py`: classificação de status
- [ ] `ui/kanban_widget.py`: UI do kanban
- [ ] `ui/deadlines_widget.py`: lista de prazos
- [ ] Notificações nativas de prazo
- [ ] `modules/preview/renderer.py`: thumbnail PNG/JPG/PDF
- [ ] `modules/preview/cache.py`: cache de thumbnails
- [ ] Command Palette com painel lateral de preview
- [ ] `modules/daily_panel/scheduler.py`: QTimer que dispara às 8h
- [ ] `modules/daily_panel/panel.py`: janela de resumo diário
- [ ] `ui/daily_panel_widget.py`: UI do painel diário
- [ ] Notificações nativas de prazo

### Fase 3 — Calculadora + Lembretes + Orçamento
**Meta:** Command Palette completo, lembretes funcionando, quoting tool integrado.

- [ ] `modules/command_palette/actions/calculator.py`: templates de cálculo
- [ ] `modules/reminders/manager.py`: lembretes com QTimer
- [ ] `modules/command_palette/actions/client_search.py`: busca de clientes
- [ ] `modules/command_palette/actions/mubisys.py`: abrir OS via URL
- [ ] Interface de configuração de templates de cálculo
- [ ] `pip install PyQt6-WebEngine` + adicionar ao `requirements.txt`
- [ ] Copiar quoting tool HTML para `data/assets/quote_tool/`
- [ ] Adicionar script `QWebChannel` ao HTML do quoting tool
- [ ] `modules/quote/bridge.py`: QObject com slots Python↔JS
- [ ] `modules/quote/panel.py`: janela QWebEngineView
- [ ] Acionar por `orc:` no Command Palette e menu da bandeja

### Fase 4 — Integrações avançadas
**Meta:** lookup de clientes, WhatsApp, integrações externas.

- [ ] Banco de clientes no SQLite + UI de cadastro
- [ ] `@nome` no Command Palette busca cliente + mostra WhatsApp
- [ ] Integração Evolution API (envio WhatsApp pelo card do kanban)
- [ ] Integração Mubisys avançada (leitura de status via scraping)

---

## Regras para o Claude Code

1. **Leia este arquivo antes de qualquer sessão.** Use `SPEC.md` como fonte de verdade sobre o projeto.
2. **Siga a estrutura de pastas definida.** Não crie arquivos fora da hierarquia acima sem justificativa.
3. **Uma feature por vez.** Implemente e teste um item da checklist antes de avançar.
4. **SQLite via `data/db.py` sempre.** Nunca acesse o banco diretamente em outros módulos.
5. **Configurações em `settings.json`.** Nada hardcoded: pastas, hotkey, thresholds de alerta.
6. **QThread para operações longas.** Busca de arquivos, sync Todoist, varredura de prazos — nunca na thread principal do Qt.
7. **Estilos apenas em `theme.qss`.** Não usar `setStyleSheet()` inline nos widgets.
8. **Ao adicionar uma feature não prevista aqui, atualizar este SPEC.md primeiro.**
