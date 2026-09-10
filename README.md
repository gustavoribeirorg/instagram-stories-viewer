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
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip
   ```

3. **Inicie o projeto usando o script pronto `run.sh`:**
   ```bash
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
   ```bash
   sudo cp stories-app.service /etc/systemd/system/
   ```

3. **Ative e inicie o serviço:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable stories-app
   sudo systemctl start stories-app
   ```

4. **Comandos úteis para gerenciar o serviço:**
   ```bash
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
```bash
docker compose up -d
```
Para acompanhar os logs:
```bash
docker compose logs -f
```

---

## 🌐 Acessando a Interface pelo Navegador do seu Computador (Host)

1. Na sua VM Ubuntu, descubra o endereço IP local:
   ```bash
   ip a | grep inet
   # ou
   hostname -I
   ```
   *(Exemplo de IP: `192.168.1.150` ou `192.168.122.50`)*

2. Se a VM tiver firewall ativo (`ufw`), libere a porta 8000:
   ```bash
   sudo ufw allow 8000/tcp
   ```

3. No navegador do seu computador host (Chrome, Edge, Firefox, etc.), acesse:
   ```text
   http://<IP_DA_VM>:8000
   ```

---

## ⚙️ Variáveis de Ambiente (`.env`)

Você pode personalizar o comportamento criando um arquivo `.env` na raiz do projeto:

```ini
HOST=0.0.0.0
PORT=8000
DATA_DIR=data
DOWNLOAD_DIR=downloads
INTERVAL_HOURS=24
REQUEST_DELAY_SECONDS=3.0
```

---

## 🧪 Executando os Testes Automatizados

Para rodar toda a suíte de testes unitários e de integração:
```bash
pytest -v
```

Testes inclusos:
- `tests/test_database.py`: Verificação de tabelas SQLite, operações de perfis e prevenção de duplicatas.
- `tests/test_scraper.py`: Teste de parsing, fallback entre provedores e detecção de perfis privados.
- `tests/test_downloader.py`: Teste de streaming atômico e integridade de arquivos.
- `tests/test_scheduler.py`: Validação do ciclo de agendamento de 24 horas.
- `tests/test_api.py`: Teste das rotas REST e interface FastAPI.
