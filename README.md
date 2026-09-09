# 📸 Instagram Stories Viewer & Auto-Downloader

Aplicação autônoma em Python para **visualização ao vivo** e **download automático a cada 24h** de stories de perfis públicos do Instagram, sem necessidade de login, conta ou cookies.

Projetada com arquitetura leve para rodar 24/7 em uma **VM Ubuntu** e acessível pelo navegador do computador host na sua rede local.

---

## 🚀 Principais Recursos

1. **Visualizador Ao Vivo (Sem Conta):**
   * Digite qualquer `@perfil_publico` e veja todos os stories ativos das últimas 24h.
   * Reprodutor nativo de vídeos em proporção 9:16 com áudio e tela cheia.
   * Galeria de fotos em alta resolução.
   * Botão para baixar mídias individuais ou todos os stories de uma vez.

2. **Rotina de Download Diário Automático (24 Horas):**
   * Cadastre perfis para monitoramento com 1 clique.
   * O sistema acorda a cada 24 horas (configurável), verifica os perfis ativos e baixa apenas os stories novos.
   * **Prevenção rigorosa de duplicidade:** mídias já baixadas são registradas no SQLite e nunca baixadas duas vezes.
   * Proteção com delay automático (3 a 5 segundos) entre perfis contra rate limit.
   * Botão **"Sincronizar Agora"** para disparar a verificação imediatamente quando quiser.

3. **Módulo de Scraping Multi-Provedor:**
   * Utiliza provedores de espelhamento público com **fallback automático**. Se um serviço oscilar, o outro assume de forma transparente.
   * Acesso direto ao Instagram via `IG_SESSIONID` (recomendado) usando `web_profile_info` com cache e retry para evitar rate limit.
   * Terceiro mirror configurável via variável de ambiente (`MIRROR_API_URL`).
   * Proxy interno de mídia (`/api/proxy-media`) para contornar bloqueios de CORS e restrições de CDN da Meta.

4. **Galeria de Mídias Salvas:**
   * Visualize todos os arquivos armazenados no disco da VM diretamente pela interface web.
   * Mídias salvas em pastas organizadas: `downloads/<perfil>/YYYY-MM-DD_HH-MM-SS_<id>.(mp4|jpg)`.

---

## 🛠️ Como Instalar e Rodar na VM Ubuntu

### Método 1: Instalação Padrão (Python venv) - Recomendado

1. **Clone ou transfira a pasta para sua VM Ubuntu:**
   ```bash
   cd ~/
   # Se transferiu via git ou scp:
   cd instagram
```

2. **Instale os pacotes básicos do sistema (se ainda não tiver):**

```
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```
3. **Inicie o projeto usando o script pronto `run.sh`:**

```
chmod +x run.sh
./run.sh
```

O servidor iniciará escutando em `0.0.0.0:8000`.

---

### Método 2: Rodar 24/7 como Serviço do Linux (`systemd`)

Para que o aplicativo inicie automaticamente com o boot da VM e reinicie sozinho em caso de falhas:

1. **Ajuste o caminho no arquivo `stories-app.service`:**
Verifique se o seu usuário e caminho batem com `/home/ubuntu/instagram`.
2. **Copie o arquivo para o systemd:**

```
sudo cp stories-app.service /etc/systemd/system/
```
3. **Ative e inicie o serviço:**

```
sudo systemctl daemon-reload
sudo systemctl enable stories-app
sudo systemctl start stories-app
```
4. **Comandos úteis para gerenciar o serviço:**

```
# Ver status
sudo systemctl status stories-app

# Ver logs em tempo real
journalctl -u stories-app -f

# Reiniciar ou Parar
sudo systemctl restart stories-app
sudo systemctl stop stories-app
```

---

### Método 3: Rodar via Docker Compose

Se tiver o Docker instalado na sua VM Ubuntu:

```
docker compose up -d
```

Para acompanhar os logs:

```
docker compose logs -f
```

---

## 🌐 Acessando a Interface pelo Navegador do seu Computador (Host)

1. Na sua VM Ubuntu, descubra o endereço IP local:

```
ip a | grep inet
# ou
hostname -I
```

*(Exemplo de IP: `192.168.1.150` ou `192.168.122.50`)*
2. Se a VM tiver firewall ativo (`ufw`), libere a porta 8000:

```
sudo ufw allow 8000/tcp
```
3. No navegador do seu computador host (Chrome, Edge, Firefox, etc.), acesse:

```
http://<IP_DA_VM>:8000
```

---

## ⚙️ Variáveis de Ambiente (`.env`)

Você pode personalizar o comportamento criando um arquivo `.env` na raiz do projeto (use `.env.example` como referência):

```
HOST=0.0.0.0
PORT=8000
DATA_DIR=data
DOWNLOAD_DIR=downloads
INTERVAL_HOURS=24
REQUEST_DELAY_SECONDS=3.0

# Credenciais (opcional, mas recomendado para acesso direto)
IG_USERNAME=
IG_PASSWORD=
IG_SESSIONID=

# Terceiro mirror configurável (Opção B)
MIRROR_API_URL=https://www.storysaver.net/api/ig/story
MIRROR_REFERER=https://www.storysaver.net/
```

### 🔑 Sobre o `IG_SESSIONID`

- O provedor direto (`DirectInstagramProvider`) usa `IG_SESSIONID` para acessar a API interna do Instagram com maior confiabilidade.
- O valor pode ser extraído dos cookies do seu navegador após login no Instagram. Geralmente no formato `1234567890%3Aabcdef...` ou `1234567890:abcdef...`.
- Com `IG_SESSIONID` configurado, o sistema resolve o perfil via `web_profile_info` (busca exata por username) e usa cache em memória por 1 hora, reduzindo rate limit.
- Em caso de erro 429, o sistema tenta automaticamente com backoff exponencial (2s → 4s → 8s).

### 🪞 Terceiro Mirror Configurável

- Se os mirrors padrão (StoriesIG e AnonyIG) falharem, o sistema tenta o endpoint definido em `MIRROR_API_URL`.
- Ajuste `MIRROR_API_URL` e `MIRROR_REFERER` para apontar para um serviço compatível com a API `/api/ig/story?url=username`.
- O formato de resposta esperado é semelhante ao dos outros mirrors (JSON com `result.stories` e `result.user`).

---

## 🧪 Executando os Testes Automatizados

Para rodar toda a suíte de testes unitários e de integração:

```
pytest -v
```

Testes inclusos:

- `tests/test_database.py`: Verificação de tabelas SQLite, operações de perfis e prevenção de duplicatas.
- `tests/test_scraper.py`: Teste de parsing, fallback entre provedores e detecção de perfis privados.
- `tests/test_downloader.py`: Teste de streaming atômico e integridade de arquivos.
- `tests/test_scheduler.py`: Validação do ciclo de agendamento de 24 horas.
- `tests/test_api.py`: Teste das rotas REST e interface FastAPI.

