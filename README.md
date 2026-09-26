# PiVoice AI

Assistente de voz de baixa latência com execução prevista em um Raspberry Pi 5.
O Windows é a estação de desenvolvimento e administração remota. O objetivo é
manter STT e TTS locais e enviar texto ao LLM da OpenAI, com documentação suficiente
para reconstruir o projeto e ensinar sua implementação.

**Estado: Fases 0, 1, 2, 3 e 4 concluídas; Fase 5 em validação.** O marco `v0.1.0`
registra a estação Windows, SSH e baseline do Raspberry Pi. A versão `v0.2.0`
entrega a fundação FastAPI e o loopback WebRTC. A versão `v0.3.0` adiciona STT
local. A versão `v0.4.0` adiciona respostas de texto da OpenAI. A Fase 5 já possui
TTS português local e retorno de voz por WebRTC implantados; falta confirmar a
experiência audível no navegador antes de publicar `v0.5.0`.

Repositório: <https://github.com/crismoraes/pi-voice-ai>

## Fase 5 — TTS local e resposta falada

Depois que a resposta textual termina, o servidor gera voz no próprio Raspberry Pi
e coloca o PCM na faixa de áudio de saída da sessão WebRTC. O texto continua sendo
o único conteúdo enviado à OpenAI.

```text
Microfone -> WebRTC -> STT local -> texto -> OpenAI
                                               |
Alto-falante <- WebRTC <- TTS local <- resposta+
```

O adaptador `TextToSpeech` separa a síntese do transporte. A implementação atual usa
`sherpa-onnx 1.13.8` com a voz Piper brasileira
`vits-piper-pt_BR-jeff-medium`, mono em 22.050 Hz. A saída é reamostrada para
48 kHz e enviada no mesmo peer WebRTC. O modelo é carregado somente na primeira
síntese, portanto `/health` não depende dele.

O modelo vem da [distribuição oficial do sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/tts/all/Portuguese/vits-piper-pt_BR-jeff-medium.html).
Ele tem cerca de 64 MB compactado e 82 MB extraído. O bootstrap executa o download
idempotente, confere o SHA-256 e mantém os arquivos em `models/`, fora do Git:

```bash
./scripts/download_tts_model.sh
```

Configuração:

| Variável | Padrão | Função |
| --- | --- | --- |
| `TTS_ENGINE` | `sherpa-piper` | Adaptador de voz local |
| `TTS_MODEL_DIR` | `models/vits-piper-pt_BR-jeff-medium` | Diretório do modelo |
| `TTS_NUM_THREADS` | `2` | Threads de inferência no Pi |
| `TTS_SPEED` | `1.0` | Velocidade da fala |
| `TTS_MAX_TEXT_CHARACTERS` | `2000` | Limite por síntese |

Para medir diretamente o modelo no Pi:

```bash
.venv/bin/python scripts/benchmark_tts.py \
  "Olá. Este é o teste da voz local do PiVoice AI." \
  --output /tmp/pi-voice-ai-tts.wav
```

O benchmark real gerou 3,036 s de voz em 0,707 s, RTF `0,233`. O verificador ao
vivo sintetizou outra frase em 0,795 s, gerou 3,882 s de áudio, RTF `0,205`, e
confirmou 185 frames audíveis recebidos no Windows pelo WebRTC:

```powershell
.\.venv\Scripts\python.exe scripts\live_tts_check.py `
  --url https://home-ai.local:8443 `
  --ca-file "$env:LOCALAPPDATA\mkcert\rootCA.pem"
```

Onze testes passaram no Windows e no Raspberry Pi ARM64. O serviço permaneceu
`active/running`, o health check HTTPS passou e os logs registraram `TTS_STARTED`,
`TTS_COMPLETED`, conexão e encerramento do peer sem erros. A conclusão da fase exige
o teste audível no navegador: atualize a página, conecte, faça uma pergunta e
confirme que a resposta aparece em texto e é reproduzida pelos alto-falantes.

## Fase 4 — resposta textual com OpenAI

Depois da transcrição local, somente o texto reconhecido é enviado pelo servidor à
Responses API da OpenAI. A resposta retorna ao navegador em eventos incrementais;
a chave fica no `.env` do Raspberry Pi e nunca é enviada ao JavaScript.

```text
Microfone -> WebRTC -> STT local -> texto -> OpenAI Responses API
                                              |
Navegador <- resposta textual em streaming <--+
```

O adaptador `LanguageModel` mantém o provedor separado da captura WebRTC e do STT.
O padrão é `gpt-6-luna`, configurável por `OPENAI_MODEL`, com respostas curtas em
português e no máximo 300 tokens. As requisições usam `store=false`, são executadas
uma por vez e não registram prompts nem respostas nos logs.

A implementação segue a documentação oficial da [Responses API para geração de
texto](https://developers.openai.com/api/docs/guides/text) e de [streaming de
respostas](https://developers.openai.com/api/docs/guides/streaming-responses).

Configuração:

| Variável | Padrão | Função |
| --- | --- | --- |
| `OPENAI_API_KEY` | vazio | Credencial mantida somente no servidor |
| `OPENAI_MODEL` | `gpt-6-luna` | Modelo de texto da Responses API |
| `OPENAI_MAX_OUTPUT_TOKENS` | `300` | Limite da resposta |
| `OPENAI_TIMEOUT_SECONDS` | `30` | Timeout da chamada externa |
| `LLM_INSTRUCTIONS` | resposta curta em português | Comportamento do assistente |

Nove testes passaram no Windows e no Raspberry Pi ARM64, incluindo streaming com
adaptadores falsos e validação de que o endpoint entrega deltas e métricas. Uma
chamada real local e outra contra a implantação HTTPS retornaram as frases
solicitadas. No Pi, o primeiro texto chegou em 1,520 s e a resposta terminou em
1,683 s.

O fluxo físico completo também passou. Uma pergunta falada sobre a chegada dos
portugueses ao Brasil gerou 7,08 s de áudio, transcritos em 0,98 s, RTF `0,14`.
Apesar de uma pequena troca de palavra no STT, o modelo interpretou a pergunta,
identificou Pedro Álvares Cabral e contextualizou que povos indígenas já habitavam o
território. O primeiro texto chegou em 1,97 s e a resposta terminou em 2,85 s. A
Fase 4 foi concluída no marco `v0.4.0`.

Na checagem final após solicitar texto simples, a implantação respondeu sem marcação
Markdown, com primeiro texto em 2,216 s e conclusão em 2,393 s.

## Fase 3 — STT local

O áudio recebido por WebRTC é duplicado com `MediaRelay`: uma faixa continua
disponível para o loopback e a outra é convertida para mono, 16 kHz e `float32`.
O usuário controla o início e o fim de cada frase. O Pi transcreve o trecho com
Whisper Tiny multilíngue quantizado por meio do `sherpa-onnx`, sem enviar áudio ou
texto a serviços externos.

```text
Navegador -> WebRTC -> MediaRelay -> buffer 16 kHz -> sherpa-onnx -> texto
                         |
                         +-> loopback opcional
```

O controle manual mantém esta fase independente de VAD. Detecção automática de
fala e endpointing serão adicionados em uma fase posterior.

### Instalação do modelo

O bootstrap instala wheels ARM64 de `sherpa-onnx 1.13.8` e `NumPy 2.4.6`, depois
executa:

```bash
./scripts/download_stt_model.sh
```

O script baixa o pacote oficial `sherpa-onnx-whisper-tiny`, valida seu SHA-256 e o
extrai em `models/`, que é ignorado pelo Git. O download tem aproximadamente 110 MB
e ocupa 245 MB depois da extração.

Configuração:

| Variável | Padrão | Função |
| --- | --- | --- |
| `STT_ENGINE` | `sherpa-whisper` | Adaptador STT local |
| `STT_MODEL_DIR` | `models/sherpa-onnx-whisper-tiny` | Diretório do modelo |
| `STT_LANGUAGE` | `pt` | Idioma Whisper |
| `STT_NUM_THREADS` | `4` | Threads de inferência no Pi |
| `STT_MIN_AUDIO_SECONDS` | `0.5` | Menor trecho aceito |
| `STT_MAX_AUDIO_SECONDS` | `30` | Limite de memória por frase |

Abra `https://home-ai.local:8443/`, conecte o microfone, clique em **Começar a
falar**, diga uma frase e clique em **Finalizar e transcrever**. A tela mostra o
texto, duração, tempo de processamento e fator de tempo real (RTF).

### Testes e benchmark

Seis testes passaram no Windows e no Raspberry Pi ARM64. O teste de integração
negocia WebRTC, captura áudio reamostrado, usa um STT substituto e valida as APIs de
início e fim da transcrição. O modelo real também foi carregado no Pi.

Nos três WAVs oficiais em inglês, com `STT_LANGUAGE=pt`, o RTF medido ficou entre
`0,203` e `0,225`; o texto não serve como medida de qualidade porque o idioma foi
forçado incorretamente. Com `STT_LANGUAGE=en`, a primeira referência foi reconhecida
corretamente em 1,134 s para 6,625 s de áudio, RTF `0,171`.

O teste da implantação enviou o mesmo WAV do Windows ao Pi por WebRTC, capturou
6,539 s e concluiu a inferência local em 1,147 s, RTF `0,175`. Os logs confirmaram
captura, carregamento do modelo, transcrição e encerramento do peer sem erros. A
validação física também passou com várias frases em português capturadas no
navegador. A última amostra produziu uma transcrição longa e compreensível sobre o
teste do sistema no Raspberry Pi 5. O Pi processou seus 18,06 s em 3,346 s, RTF
`0,185`. O Whisper Tiny cometeu alguns erros de palavras, registrados como uma
limitação de qualidade do modelo pequeno.

Para repetir um benchmark:

```bash
.venv/bin/python scripts/benchmark_stt.py caminho/para/audio.wav
```

Para validar uma implantação completa com um WAV enviado por WebRTC:

```powershell
.\.venv\Scripts\python.exe scripts\live_stt_check.py `
  --url https://home-ai.local:8443 `
  --ca-file "$env:LOCALAPPDATA\mkcert\rootCA.pem" `
  --audio-file caminho\para\audio.wav
```

## Fase 2 — loopback de áudio WebRTC

Estado atual: implementação, deployment HTTPS, validação automatizada do transporte
e teste audível com microfone e alto-falante reais concluídos.

```text
Microfone do navegador
        |
        | WebRTC: ICE + DTLS + SRTP
        v
FastAPI signaling -> aiortc no Raspberry Pi
        |
        | mesma faixa de áudio retornada
        v
Alto-falante do navegador
```

O navegador usa `POST /api/webrtc/offer` para trocar SDP e recebe um identificador
do peer. Ao encerrar, usa `DELETE /api/webrtc/peers/{peer_id}`. O servidor mantém
as conexões em memória e fecha todas no shutdown. Esta fase apenas devolve o áudio;
ela ainda não executa VAD, STT, OpenAI ou TTS.

O cliente web é servido pela própria aplicação. Depois do deployment TLS, abra:

```text
https://home-ai.local:8443/
```

Use fones de ouvido para evitar microfonia. Clique em **Iniciar loopback**, permita
o microfone e fale. O áudio deve voltar pelo elemento de áudio do navegador. O
cliente desativa cancelamento de eco, supressão de ruído e ganho automático apenas
para tornar o loopback verificável.

### HTTPS local

APIs de microfone exigem contexto seguro. Para desenvolvimento foi escolhido
`mkcert`, sem desativar proteções do navegador. No Windows, a CA local foi instalada
no armazenamento confiável e o certificado foi criado fora do repositório para o
hostname do Pi. Ele expira em dezembro de 2028.

Arquivos locais:

```text
%USERPROFILE%\.config\pi-voice-ai\tls\server.pem
%USERPROFILE%\.config\pi-voice-ai\tls\server-key.pem
%LOCALAPPDATA%\mkcert\rootCA.pem
```

Destino no Pi:

```text
/home/<usuario>/.config/pi-voice-ai/tls/
```

A chave TLS e a CA ficam fora do Git. O diretório remoto usa permissão `700`; a
chave, `600`, e os certificados públicos, `644`. O `.env` do Pi aponta para esses
arquivos e usa `APP_PORT=8443`. O health check usa o hostname do Pi com `--resolve`
para acessar `127.0.0.1`, mantendo a validação da CA e do nome do certificado.

O servidor não possui autenticação de usuários nesta fase. Mantenha-o na rede local;
não encaminhe a porta no roteador nem o exponha à internet.

### Validação automatizada

```powershell
.\.venv\Scripts\python.exe -m pytest -vv
.\.venv\Scripts\python.exe scripts\live_webrtc_check.py `
  --url https://home-ai.local:8443 `
  --ca-file "$env:LOCALAPPDATA\mkcert\rootCA.pem"
```

O teste de integração cria dois peers reais, negocia ICE/DTLS/SRTP e exige que um
frame de áudio retorne pelo loopback. Três testes foram aprovados no Windows com
Python 3.12 e no Raspberry Pi ARM64 com Python 3.13, incluindo `/health`, página
web e transporte de áudio. Os wheels WebRTC foram instalados sem compilação nativa.

O processo HTTPS também foi iniciado localmente em 8443 com o certificado gerado.
Uma consulta usando `home-ai.local`, validação de cadeia e validação de hostname
recebeu o JSON de saúde esperado. O processo temporário foi encerrado e a porta
8443 voltou a ficar livre.

No deployment do Pi, o serviço ficou `active` e `enabled`, sem avisos recentes no
journald. `/health` e a página web responderam por HTTPS a partir do Windows. O
verificador ao vivo negociou ICE, DTLS e SRTP, recebeu um frame de áudio devolvido
pelo Pi e removeu o peer com sucesso. Os logs confirmaram conexão e desconexão.
O teste manual no navegador também passou: o usuário autorizou o microfone e ouviu
a própria voz retornando corretamente pelos alto-falantes.

## Fase 1 — fundação HTTP

A fundação implementada fornece uma aplicação FastAPI mínima e independente de
OpenAI ou hardware de áudio:

```text
systemd -> Python virtual environment -> Uvicorn -> FastAPI -> GET /health
                                                  |
                                                  +-> JSON logs -> journald
```

O endpoint responde exatamente:

```json
{"status":"ok"}
```

Dependências diretas estão fixadas em `pyproject.toml`: FastAPI 0.141.1,
Uvicorn 0.53.0 e pydantic-settings 2.15.0. As dependências de desenvolvimento são
pytest 8.4.2 e HTTPX 0.28.1. Python 3.11 ou superior é exigido.

Para preparar o ambiente no Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m app.main
```

Em outro terminal, valide:

```powershell
curl.exe --fail http://127.0.0.1:8000/health
```

O teste local real passou em Python 3.12.0. O teste ASGI retornou HTTP 200 e o JSON
esperado; a compilação de `app` e a sintaxe de todos os scripts Bash também passaram.

### Instalação no Raspberry Pi

Em um Pi novo, clone o repositório como o usuário que executará o serviço:

```bash
cd "$HOME"
git clone https://github.com/crismoraes/pi-voice-ai.git
cd pi-voice-ai
./scripts/bootstrap_pi.sh
```

O bootstrap verifica a arquitetura ARM64 e instala somente pacotes ausentes entre
Git, Python, venv, pip e curl. Depois cria `.venv`, instala o projeto com ferramentas
de teste e cria um `.env` local com permissão `600` quando ele ainda não existe.

Não copie o `.env` do Windows pelo Git. A chave OpenAI não é necessária na Fase 1.
Quando for necessário configurar o Pi, edite o `.env` diretamente nele. O arquivo
continua ignorado pelo Git.

Para instalar e validar o serviço:

```bash
cd "$HOME/pi-voice-ai"
./scripts/deploy.sh
```

O deployment para quando encontra mudanças locais, atualiza somente por fast-forward,
executa bootstrap, compilação e testes, renderiza o serviço para o usuário e caminho
reais, reinicia a aplicação, consulta `/health`, mostra o estado e inspeciona erros
recentes do journald.

### Operação

```bash
./scripts/start.sh
./scripts/stop.sh
./scripts/restart.sh
./scripts/healthcheck.sh
sudo systemctl status pi-voice-ai
sudo journalctl -u pi-voice-ai -f
```

Configuração lida nesta fase:

| Variável | Padrão | Função |
| --- | --- | --- |
| `APP_HOST` | `0.0.0.0` | Interface HTTP |
| `APP_PORT` | `8000` | Porta HTTP |
| `LOG_LEVEL` | `INFO` | Nível dos logs JSON |
| `TLS_CERT_FILE` | vazio | Certificado HTTPS do servidor |
| `TLS_KEY_FILE` | vazio | Chave privada HTTPS, fora do Git |
| `TLS_CA_FILE` | vazio | CA usada pelo health check HTTPS |

O endpoint de saúde não depende da internet nem da OpenAI. HTTP é suficiente para
a validação da Fase 1 na rede local; HTTPS será configurado antes do uso do microfone
do navegador em fases posteriores.

### Estado da implantação no Pi

O clone foi criado em `/home/cristiano/pi-voice-ai`. O bootstrap confirmou que as
ferramentas do sistema já estavam disponíveis, criou `.venv` com Python 3.13,
instalou as dependências ARM64 e gerou o `.env` local vazio com permissão `600`.
O teste remoto e a compilação passaram. Um servidor temporário respondeu
`{"status":"ok"}` pela rede e foi encerrado; a porta 8000 ficou livre novamente.

A instalação systemd foi concluída com a senha sudo digitada pelo usuário em seu
próprio terminal. O serviço está habilitado e ativo. Para repetir o deployment:

```powershell
ssh -t voicepi "cd ~/pi-voice-ai && ./scripts/deploy.sh"
```

O script pede a senha no terminal quando necessária. Não registre a senha em
arquivos, comandos, logs ou documentação.

Validação final: serviço `active/running` e `enabled`, processo executado como
`cristiano`, `ExecMainStatus=0`, nenhum restart, nenhum erro recente no journald e
health check aprovado tanto no próprio Pi quanto pela rede. A unidade está habilitada
para iniciar no boot; um reboot real do Pi ainda não foi realizado nesta fase.

## Arquitetura

Na Fase 0, a conexão que estamos preparando é:

```text
Windows: VS Code + PowerShell + Git
                 |
                 | SSH, alias voicepi
                 v
Raspberry Pi 5: futuro ambiente de execução
```

Arquitetura implementada até a Fase 5:

```text
Microfone do navegador -> WebRTC -> Raspberry Pi 5
                                      |
                             VAD -> STT local
                                      |
                                 LLM de texto
                                      |
                                  TTS local
                                      |
Alto-falante do navegador <- WebRTC <--+
```

Futuramente, adaptadores USB poderão substituir a entrada e a saída WebRTC sem
reescrever a lógica de conversação. O alvo validado é um Raspberry Pi 5 Model B
Rev 1.0, ARM64, executando Debian GNU/Linux 13 com kernel Raspberry Pi.

## Resultados confirmados nesta sessão

| Verificação | Resultado |
| --- | --- |
| Windows | Windows 11 Home, 64 bits; versão 10.0.26200; registro 25H2, build 26200.9445 |
| PowerShell | Windows PowerShell 5.1.26100.9444, Desktop |
| OpenSSH | OpenSSH_for_Windows_9.5p2, LibreSSL 3.8.2 |
| Git | 2.49.0.windows.1 |
| VS Code | 1.136.1, x64; janela aberta na pasta pai RaspberryPI5 |
| Configuração de editor no clone | Nenhum `.vscode` ou arquivo `.code-workspace` encontrado |
| Git local | Branch `main`, commits da Fase 0 criados após revisão de conteúdo sensível |
| GitHub | `origin/main` criado e configurado como upstream, sem reescrever histórico |
| Chaves SSH | Par ED25519 `pi-voice-ai` criado; fingerprint local e remota coincidem |
| Alias `voicepi` | Criado no SSH do Windows e validado com comando remoto |
| `ssh-agent` do Windows | Parado e desabilitado; não alterado |
| Pendrive | Consulta não encontrou volumes classificados como removíveis |
| Fundação local | Seis arquivos obrigatórios presentes; exemplos de segredos ignorados; índice Git vazio |
| Raspberry Pi | Pi 5 Model B Rev 1.0; `home-ai`; Debian 13; aarch64; autenticação por chave validada |
| Recursos do Pi | 7,9 GiB RAM; raiz de 29 GB com 21 GB livres; 40,6 °C; sem throttling |
| Software do Pi | Kernel 6.18.50+rpt-rpi-2712; Python 3.13.5; Git 2.47.3 |
| Repositório no Pi | `~/pi-voice-ai` ainda não existe; nenhuma aplicação está implantada |

A listagem remota confirma acesso de leitura, não permissão de push. Identificadores
da máquina, endereços privados e conteúdos das chaves não são registrados aqui.

## Recriar a preparação do Windows

Os comandos desta seção são um **procedimento de reprodução**, não uma declaração
de que todas as etapas já foram executadas. Resultados observados estão na tabela
acima; o registro didático fica em [Curso_Step.md](Curso_Step.md).

Em uma instalação nova, tenha Git, OpenSSH Client e VS Code disponíveis. Inspecione:

```powershell
$PSVersionTable
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture
Get-Command ssh,ssh-keygen,git,code
ssh -V
git --version
code --version
```

Para obter o projeto em outra máquina:

```powershell
git clone https://github.com/crismoraes/pi-voice-ai.git
Set-Location pi-voice-ai
git status
git remote -v
```

No clone existente, entre diretamente na pasta `pi-voice-ai`. A pasta pai
`RaspberryPI5` não é a raiz Git. Não execute outro `git init` nela.

## Chaves SSH: verificar antes de gerar

```powershell
Get-ChildItem -LiteralPath (Join-Path $env:USERPROFILE '.ssh') -Force
```

`id_ed25519` é a **chave privada**: deve permanecer no Windows, fora do repositório
e do pendrive. `id_ed25519.pub` é a **chave pública**: pode ser instalada no Pi.
ED25519 é o tipo de chave usado para comprovar a identidade do cliente SSH.

Se já existir um par adequado, preserve-o. Nesta sessão, o par encontrado pertencia
a outro projeto e foi preservado. O usuário criou o par próprio `id_ed25519` para
PiVoice AI no caminho padrão. A impressão digital da chave pública foi confirmada
localmente e no `authorized_keys` do Pi, sem registrar seu conteúdo.

Quando a criação de uma nova chave for necessária, execute no terminal local:

```powershell
ssh-keygen -t ed25519 -C "pi-voice-ai"
```

Aceite o caminho padrão somente se ele estiver livre. Se aparecer uma pergunta
para sobrescrever, responda `n` e confira o arquivo existente. Escolha a frase-senha
diretamente no terminal; não a envie ao chat nem a registre na documentação.
Uma frase-senha protege a chave privada. O `ssh-agent` pode mantê-la desbloqueada
na sessão, mas sua configuração não foi realizada nesta etapa.

Depois de gerar, confira apenas a chave pública:

```powershell
ssh-keygen -lf (Join-Path $env:USERPROFILE '.ssh\id_ed25519.pub')
```

## Transferência por pendrive

Se a instalação da chave no Pi ainda for necessária, conecte o pendrive ao Windows
e confirme a letra no Explorador de Arquivos. Copie **somente**
`%USERPROFILE%\.ssh\id_ed25519.pub`. O arquivo sem `.pub` deve ficar no Windows.

Exemplo interativo, após conferir a unidade:

```powershell
$usbRoot = Read-Host 'Raiz do pendrive confirmada no Explorador (ex.: E:\)'
$publicKey = Join-Path $env:USERPROFILE '.ssh\id_ed25519.pub'
$destination = Join-Path $usbRoot 'id_ed25519.pub'
if (-not (Test-Path -LiteralPath $usbRoot -PathType Container)) { throw 'Unidade não encontrada' }
if (Test-Path -LiteralPath $destination) { throw 'Arquivo já existe: confira antes de substituir' }
Copy-Item -LiteralPath $publicKey -Destination $destination
Get-FileHash -LiteralPath $publicKey,$destination -Algorithm SHA256
```

Os hashes devem ser iguais. Ejete o pendrive e conecte-o ao Pi. No Pi, localize o
arquivo pelo gerenciador de arquivos ou consulte `lsblk -f` e `findmnt`. Não presuma
um caminho de montagem. Confirme o caminho real antes da próxima etapa.

## Instalar a chave no Raspberry Pi

Execute como o usuário Linux que será usado na conexão SSH. O bloco abaixo é para
**Bash no Pi** e usa o caminho informado pelo operador. Não o execute no PowerShell.

```bash
install_public_key() {
    local public_key key_type key_blob key_comment
    read -r -p 'Caminho completo do id_ed25519.pub no pendrive: ' public_key
    test -f "$public_key" || { printf 'Arquivo não encontrado\n'; return 1; }
    ssh-keygen -lf "$public_key" || return 1
    read -r key_type key_blob key_comment < "$public_key"
    test "$key_type" = ssh-ed25519 && test -n "$key_blob" || return 1
    mkdir -p "$HOME/.ssh" || return 1
    chmod 700 "$HOME/.ssh" || return 1
    touch "$HOME/.ssh/authorized_keys" || return 1
    chmod 600 "$HOME/.ssh/authorized_keys" || return 1
    if awk -v blob="$key_blob" '
        /^[[:space:]]*#/ { next }
        { for (i = 1; i < NF; i++)
            if ($i == "ssh-ed25519" && $(i+1) == blob) found = 1 }
        END { exit !found }
    ' "$HOME/.ssh/authorized_keys"; then
        printf 'Chave já instalada\n'
    else
        printf '\n%s %s\n' "$key_type" "$key_blob" >> "$HOME/.ssh/authorized_keys" || return 1
    fi
    ls -ld "$HOME/.ssh"
    ls -l "$HOME/.ssh/authorized_keys"
}
install_public_key
```

A comparação considera o material da chave, independentemente do comentário,
para evitar duplicatas e preservar outras entradas. A permissão `700` permite
acesso ao diretório apenas ao proprietário; `600` permite leitura e escrita do
arquivo apenas ao proprietário. A instalação não modifica `sshd_config` e não
desabilita autenticação por senha. A instalação foi concluída pelo usuário; a
validação remota confirmou `700` em `~/.ssh`, `600` em `authorized_keys` e a mesma
impressão digital observada no Windows.

## Conexão direta e alias `voicepi`

Obtenha o usuário e endereço reais do Pi. No primeiro acesso, compare a impressão
digital apresentada pelo SSH com a do próprio Pi antes de aceitar a identidade do
servidor. A chave do servidor é diferente da chave do usuário recém-instalada.

No PowerShell, substitua os campos entre `<...>`:

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" <pi-user>@<pi-host>
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" <pi-user>@<pi-host> "hostname"
```

Depois do acesso direto funcionar, acrescente a entrada abaixo a
`%USERPROFILE%\.ssh\config`, preservando outras entradas. Caso `voicepi` já exista,
revise sua configuração antes de alterá-la.

```sshconfig
Host voicepi
    HostName <pi-host>
    User <pi-user>
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

Abra e encerre uma sessão; depois abra uma nova e teste comandos:

```powershell
ssh voicepi
ssh voicepi "hostname"
ssh -o IdentitiesOnly=yes -o PreferredAuthentications=publickey voicepi "hostname"
ssh voicepi "hostname && uname -m && python3 --version && free -h && df -h /"
```

As opções no terceiro comando limitam a conexão à autenticação por chave e às
identidades configuradas, evitando selecionar outra chave do agente. Não alteram a configuração do
servidor. Se houver frase-senha, ela poderá ser solicitada localmente.

Nesta máquina, o teste direto com `BatchMode=yes` respondeu `home-ai`, comprovando
que a autenticação por chave funciona sem fallback para senha. O arquivo SSH do
Windows não existia e foi criado somente com a entrada `voicepi`. Tanto
`ssh voicepi "hostname"` quanto o comando básico de inventário foram executados
com sucesso. O endereço privado real permanece apenas na configuração local.

## Inventário do Pi

Após validar SSH, execute no Pi, por SSH, cada comando abaixo. Registre comandos
ausentes como indisponíveis e continue a coleta; não instale pacotes automaticamente.

```bash
hostname
hostname -I
uname -a
uname -m
cat /etc/os-release
python3 --version
git --version
free -h
df -h /
vcgencmd measure_temp
vcgencmd get_throttled
```

Resultados coletados: Raspberry Pi 5 Model B Rev 1.0, hostname `home-ai`, Debian
GNU/Linux 13 (trixie), kernel `6.18.50+rpt-rpi-2712`, arquitetura `aarch64`, Python
3.13.5 e Git 2.47.3. Foram observados 7,9 GiB de RAM, 2 GiB de swap sem uso e uma
raiz de 29 GB com 21 GB livres. A temperatura foi 40,6 °C e `get_throttled`
retornou `0x0`. O endereço privado foi conferido, mas não é publicado. O diretório
`~/pi-voice-ai` não existia, portanto ainda não havia estado ou versão da aplicação
para consultar.

## Configuração futura

`.env.example` é apenas um modelo para fases posteriores. Chaves SSH nunca devem
ser armazenadas no `.env`: a privada fica em `%USERPROFILE%\.ssh`, e a pública no
`~/.ssh/authorized_keys` do usuário remoto. Nenhuma chave OpenAI é
necessária na Fase 0. Quando houver necessidade de configuração local, copie sem
sobrescrever um arquivo existente:

```powershell
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
git check-ignore -v .env
```

| Variável | Uso previsto |
| --- | --- |
| `OPENAI_API_KEY` | Credencial do backend, vazia no exemplo |
| `AUDIO_MODE` | Adaptador de áudio; `webrtc` inicialmente |
| `APP_HOST`, `APP_PORT` | Endereço de escuta e porta futuros |
| `STT_ENGINE` | `sherpa-whisper` selecionado e medido no ARM64 |
| `TTS_ENGINE` | `sherpa-piper`, selecionado e medido no ARM64 |
| `LOG_LEVEL` | Nível de logs |
| `ENABLE_BARGE_IN` | Interrupção da resposta por fala do usuário |
| `ENABLE_PARTIAL_TRANSCRIPTS` | Transcrições parciais |
| `ENABLE_STREAMING_LLM` | Respostas incrementais do LLM |

## Validação e versionamento

Antes do commit inicial, validar chave, instalação no Pi, alias, comandos remotos,
inventário, documentação e exclusão de segredos pelo Git. Acesso SSH e inventário
do Pi ainda impedem considerar a Fase 0 concluída.

```powershell
git status
git diff
git ls-files
git diff --cached --name-only
git check-ignore -v .env .venv/placeholder __pycache__/placeholder.pyc id_ed25519 secrets/placeholder private/placeholder
```

Arquivos novos ainda não rastreados não aparecem em `git diff`; leia-os antes de
adicionar explicitamente os seis arquivos da fundação. Revise `git diff --cached`
antes do commit. Não há testes de aplicação nesta fase; os checks são de ambiente,
SSH, Git e documentação.

Nesta preparação, `git status`, `git diff`, `git diff --check`, `git ls-files` e a
consulta ao índice foram executados. Os seis arquivos continuam não rastreados,
sem nada staged. `git check-ignore` confirmou exclusão de `.env`, `.env.local`,
ambiente virtual, cache Python, chaves e diretórios privados; os seis arquivos da
fundação não estão ignorados. Uma busca por padrões comuns de credenciais e chaves
privadas nesses arquivos não encontrou correspondências. Nenhum `.env` foi criado.

Somente depois de todos os critérios passarem, preparar o commit
`chore: initialize PiVoice AI development environment` e fazer push seguro, sem
reescrever histórico remoto. Antes de criar `v0.1.0`, apresentar os arquivos,
validações, inventário e pendências ao usuário. O commit inicial
`chore: initialize PiVoice AI development environment` foi criado e enviado para
`origin/main`, e a release `v0.1.0` foi publicada.

## Problemas realmente encontrados

- Ao tentar preparar a chave, foi executado `ssh-keygen -lf` com o nome
  `id\_ed25519.pub`, resultando em `No such file or directory`. A barra antes de
  `_` altera o caminho; o nome correto é `id_ed25519.pub`. Além disso, `-lf` apenas
  mostra a impressão digital de uma chave existente. A inspeção de 2026-09-24
  confirmou que nem `id_ed25519` nem `id_ed25519.pub` existiam no local padrão.
  Primeiro é necessário gerar o par com `ssh-keygen -t ed25519 -C "pi-voice-ai"`;
  depois, verificar a chave pública com o comando da seção de chaves SSH. A chave
  foi posteriormente criada, instalada e validada no Pi.
- Comandos Git na pasta pai retornaram `not a git repository`. O clone está na
  subpasta `pi-voice-ai`; usar essa pasta como diretório de trabalho resolve.
- Ler `AGENTS.md` por caminho relativo, fora da raiz do clone, falhou. A leitura
  completa funcionou ao especificar o diretório do repositório.
- A consulta inicial a `.ssh` recebeu `Access is denied`. Isso não significa que
  o diretório não exista. A consulta autorizada fora da restrição mostrou os arquivos.
- O acesso inicial ao GitHub falhou na porta 443. A mesma consulta remota funcionou
  com permissão de rede; não foi necessário mudar o remote nem credenciais.
- Consultas CIM/volumes foram bloqueadas inicialmente e funcionaram com a permissão
  necessária. O registro reportou `Windows 10 Home`, mas o CIM confirmou Windows 11
  Home. Documentamos o resultado do CIM e os números de build observados.
- `code --version` retornou a versão, junto de aviso `CreateFile: Access is denied`
  do Crashpad. A janela do VS Code foi detectada; o aviso não foi corrigido.

- O primeiro teste SSH feito dentro da restrição local não conseguiu acessar a
  chave nem a porta 22. Repetido com a permissão SSH prevista para o projeto, o Pi
  respondeu `home-ai`; o bloqueio era do ambiente de execução local.
- O Pi não permite `sudo -n`, portanto a instalação systemd não pode ser concluída
  por uma sessão automatizada sem interação. A solução é executar `deploy.sh` com
  `ssh -t` e digitar a senha sudo apenas no terminal local.
- Na primeira instalação, o serviço iniciou corretamente, mas o health check foi
  executado antes de o Uvicorn abrir a porta e o deployment terminou com
  `curl: (7)`. A verificação posterior mostrou o serviço ativo e HTTP 200. O script
  passou a repetir a consulta por até 20 segundos antes de declarar falha.
- O curl do Windows não conseguiu consultar revogação para a CA privada do mkcert
  e retornou `CRYPT_E_NO_REVOCATION_CHECK`. O teste foi repetido com
  `--ssl-no-revoke`, preservando validação de cadeia e hostname, e passou. Não foi
  usado `--insecure`.
- Após o teste temporário, `Ctrl+C` encerrou a sessão SSH antes de encerrar o
  servidor remoto. O processo exato foi identificado pelo PID, finalizado com
  `SIGTERM` e a porta 8000 foi confirmada como livre.
