# PiVoice AI — registro para o curso

## Fase 0 — Preparando acesso SSH do Windows ao Raspberry Pi 5

**Aula concluída.** A inspeção do Windows e do Git, criação e instalação da chave,
conexão SSH, alias `voicepi` e inventário do Pi foram realizados e registrados no
marco `v0.1.0`.

### Objetivo da aula

Preparar uma estação Windows para administrar o Raspberry Pi por SSH e manter no
Git um registro reproduzível do projeto. Ao final da Fase 0, o aluno deverá
conseguir executar comandos no Pi usando `ssh voicepi` e explicar como a chave
pública autoriza a chave privada mantida no Windows.

### Conceitos e arquitetura

SSH permite executar comandos em outra máquina por uma conexão protegida. O
Windows contém editor, cliente SSH e ferramentas de versionamento. O Pi é o alvo
de execução; ter as ferramentas no Windows não comprova sua presença no Pi.

Antes da preparação: clone local e Raspberry Pi sem conexão validada.

Resultado arquitetural validado:

```text
Windows: editor + Git + chave privada
                 |
                 | SSH com alias voicepi
                 v
Pi: ~/.ssh/authorized_keys contém a chave pública
```

ED25519 é o tipo de chave escolhido. O par contém uma chave privada, que comprova
a identidade, e uma chave pública, que o servidor pode aceitar. O sufixo `.pub`
identifica o arquivo transferível. A chave privada fica fora do repositório e do
pendrive. Uma frase-senha protege a chave privada; é digitada localmente e nunca
registrada na aula. O usuário escolhe usá-la ou não.

O Git registra o histórico local. O remote `origin` associa o clone ao GitHub;
configurar a URL não comprova autenticação nem permissão para enviar commits.
Arquivos não rastreados também precisam ser revisados: `git diff` sozinho não os
exibe.

### Implementação realizada e comandos executados

1. O pedido da Fase 0 e o `AGENTS.md` completo foram lidos antes das alterações.
2. O clone foi inspecionado: continha `.git` e o `AGENTS.md` fornecido pelo usuário.
3. Foram consultadas as versões das ferramentas e a janela do VS Code.
4. A pasta SSH foi listada sem ler conteúdo de chaves privadas. A chave pública
   existente foi inspecionada com `ssh-keygen -lf`.
5. O GitHub foi consultado sem alteração remota.
6. Foram criados README, este registro, changelog, `.gitignore` e `.env.example`.

Comandos de inspeção efetivamente executados, agrupados por finalidade:

```powershell
Get-Content -LiteralPath 'AGENTS.md' -Raw -Encoding UTF8
git status --short --branch
git remote -v
git ls-files
git diff --cached --name-only
git config --get user.name
git config --get user.email
git ls-remote --symref origin
```

A identidade Git existente foi consultada e preservada; seus dados pessoais não
são reproduzidos aqui. A listagem remota terminou com código zero e sem referências:
o remoto estava vazio. A branch local era `main`, sem commits.

```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' | Select-Object ProductName,DisplayVersion,CurrentBuild,UBR
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture | ConvertTo-Json
Get-Command ssh,ssh-keygen,git,code -ErrorAction SilentlyContinue | Select-Object Name,Source
ssh -V
git --version
code --version
Get-Process -Name Code -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle } | Select-Object ProcessName,MainWindowTitle | ConvertTo-Json
```

Resultados: Windows 11 Home 64 bits, build 26200.9445 / 25H2; PowerShell
5.1.26100.9444; OpenSSH 9.5p2; Git 2.49.0.windows.1; VS Code 1.136.1 x64. A janela
do editor estava aberta na pasta pai `RaspberryPI5`. Nenhuma configuração `.vscode`
ou `.code-workspace` foi encontrada no clone.

```powershell
$sshDir = Join-Path $env:USERPROFILE '.ssh'
Get-ChildItem -LiteralPath $sshDir -Force | Select-Object Name,Length,Mode | ConvertTo-Json
Get-ChildItem -LiteralPath $sshDir -Filter '*.pub' -File | ForEach-Object { ssh-keygen -lf $_.FullName }
Get-Service ssh-agent -ErrorAction SilentlyContinue | Select-Object Name,Status,StartType
Get-Volume | Where-Object { $_.DriveType -eq 'Removable' } | Select-Object DriveLetter,FileSystemType,Size,SizeRemaining | ConvertTo-Json
```

Foi encontrado um par ED25519 cujo nome indica outro projeto, além dos arquivos
de hosts conhecidos. Não havia `id_ed25519`, `id_ed25519.pub` nem `config`. O serviço
`ssh-agent` estava parado/desabilitado. A consulta não encontrou volume classificado
como removível; isso não identifica um caminho de montagem no Raspberry Pi.

### Continuação da aula — ainda não executada

A criação, transferência e instalação descritas abaixo foram concluídas. O
[README](README.md) mantém os procedimentos de reprodução. A escolha e o conteúdo
da frase-senha não foram registrados.

A transferência USB terá três passos físicos: identificar a unidade no Windows,
copiar somente `id_ed25519.pub` e conectar o pendrive ao Pi. A chave privada
`id_ed25519` permanecerá no Windows. O caminho do arquivo no Pi deve ser confirmado
no próprio Pi; não pode ser inferido da letra da unidade no Windows.

No Linux, o diretório `.ssh` usará permissão `700` e o arquivo `authorized_keys`
usará `600`. Em `700`, apenas o dono pode listar, modificar e atravessar o diretório.
Em `600`, apenas o dono pode ler e escrever o arquivo. A instalação deve preservar
as entradas existentes e comparar o material da chave para evitar duplicatas,
mesmo se o comentário da chave mudar.

Depois da instalação, será validado primeiro o acesso direto ao usuário/endereço
real e depois o alias `voicepi`. O alias reúne hostname, usuário e caminho da chave
no arquivo SSH do Windows. A autenticação por chave será testada em novas conexões,
mantendo a autenticação por senha habilitada no servidor.

Com o acesso validado, os comandos remotos forneceram SO, arquitetura, Python,
Git, RAM, disco, temperatura e throttling. Não houve benchmark de áudio ou modelos.

### Problemas reais, diagnóstico e verificação

| Problema observado | Diagnóstico / ação | Verificação |
| --- | --- | --- |
| `not a git repository` na pasta pai | O clone fica em `pi-voice-ai`; especificar essa pasta | `git status` identificou `main` |
| Leitura relativa de `AGENTS.md` falhou | Diretório de trabalho incorreto; especificar a raiz do clone | Arquivo completo lido com UTF-8 |
| `Access is denied` ao consultar `.ssh` | Restrição do ambiente; repetir leitura com permissão | Diretório e chave pública puderam ser inspecionados |
| Falha de conexão ao GitHub na porta 443 | Repetir consulta com permissão de rede | `git ls-remote` terminou com código zero |
| CIM e volumes retornaram acesso negado | Executar consultas autorizadas fora da restrição | Windows identificado e consulta de volumes concluída |
| Registro chamou o SO de Windows 10 Home | Conferir o nome via CIM | CIM confirmou Windows 11 Home |
| Aviso Crashpad de acesso negado em `code --version` | A versão ainda foi retornada; consultar janela do editor | VS Code detectado; aviso permanece sem correção |

Uma primeira tentativa com `Test-Path` chegou a emitir indicação de diretório
ausente após erro de permissão. Essa indicação foi descartada: falha de acesso
não comprova ausência. A repetição usou erros terminantes e confirmou o diretório.

### Testes, resultado esperado e resumo

O ambiente local possui as ferramentas necessárias, o clone aponta para o remoto
correto e os critérios de chave, alias, comando remoto e inventário foram atendidos.

Naquele ponto, o commit inicial, push e `v0.1.0` ainda aguardavam a validação
completa da Fase 0. Eles foram concluídos antes do início da Fase 1.

Verificações locais efetivamente executadas após criar a fundação:

```powershell
git status --short --branch
git diff --check
git diff
git ls-files
git diff --cached --name-only
```

Também foi executado `git check-ignore -v --` para cada caminho de exemplo de
segredo/arquivo gerado e `git check-ignore -q --` para cada arquivo da fundação.
Foram verificados `.env`, `.env.local`, `.venv`, cache Python, extensões `.pyc`,
`.key` e `.pem`, diretórios `secrets`, `private`, `.ssh` e nomes de chaves ED25519.
Todos os exemplos privados foram ignorados e os seis arquivos obrigatórios
permaneceram disponíveis para versionamento. Uma busca de padrões comuns de
credenciais e marcadores de chave privada não encontrou correspondências.

Resultado: seis arquivos não rastreados, nenhum arquivo no índice, nenhum arquivo
já rastreado e nenhum `.env` criado. O `git diff` vazio é esperado antes de adicionar
arquivos; não significa que não haja documentos novos. Um `debug.log` gerado durante
a inspeção está excluído pela regra de logs. O comando de validação terminou com
`FOUNDATION_CHECKS_PASS`, que se refere somente à fundação local, não à Fase 0 inteira.

### Continuação em 2026-09-24 — verificação antes da geração da chave

O usuário relatou `No such file or directory` ao executar:

```powershell
ssh-keygen -lf (Join-Path $env:USERPROFILE '.ssh\id\_ed25519.pub')
```

O comando usa um caminho incorreto: há uma barra antes do sublinhado. O nome
correto é `id_ed25519.pub`. A opção `-lf` exibe a impressão digital de um arquivo
existente e não cria o par de chaves.

Para confirmar o estado real, foram executadas estas verificações, sem ler a
chave privada:

```powershell
$sshDir = Join-Path $env:USERPROFILE '.ssh'
$privatePath = Join-Path $sshDir 'id_ed25519'
$publicPath = Join-Path $sshDir 'id_ed25519.pub'
[pscustomobject]@{PrivateKeyExists=(Test-Path -LiteralPath $privatePath -PathType Leaf);PublicKeyExists=(Test-Path -LiteralPath $publicPath -PathType Leaf)} | ConvertTo-Json
```

Ambos os resultados eram `false`. Foi orientado gerar o par no terminal local,
escolhendo ali a frase-senha, e somente depois verificar a chave pública usando o
nome correto. Posteriormente, os dois arquivos passaram a existir e a chave pública
foi validada como ED25519 com o comentário `pi-voice-ai`.

### Continuação em 2026-09-25 — instalação e validação SSH

O usuário copiou `id_ed25519.pub` para o Raspberry Pi e informou que o SSH estava
ativo. A chave SSH não foi colocada no `.env`: a privada permaneceu no diretório
OpenSSH do Windows e a pública foi instalada em `~/.ssh/authorized_keys`.

O primeiro teste automatizado, dentro da restrição local, falhou ao acessar a chave
e a porta 22. Ao executar o mesmo teste com a permissão SSH prevista no projeto, a
conexão por chave respondeu com o hostname `home-ai`. O teste usou `BatchMode=yes`,
portanto não recorreu a uma senha interativa. A impressão digital do
`authorized_keys` coincidiu com a chave pública local.

O arquivo `%USERPROFILE%\.ssh\config`, antes ausente, foi criado com o alias
`voicepi`, preservando a chave privada fora do repositório:

```sshconfig
Host voicepi
    HostName <endereço privado do Pi>
    User cristiano
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

Foram executados com sucesso:

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=8 voicepi "hostname"
ssh -o BatchMode=yes -o ConnectTimeout=8 voicepi "hostname && uname -m && python3 --version && free -h && df -h /"
```

Inventário observado: Raspberry Pi 5 Model B Rev 1.0; hostname `home-ai`; Debian
GNU/Linux 13 (trixie); kernel `6.18.50+rpt-rpi-2712`; `aarch64`; Python 3.13.5;
Git 2.47.3; 7,9 GiB de RAM; 2 GiB de swap sem uso; raiz de 29 GB com 21 GB livres;
40,6 °C; `throttled=0x0`. As permissões eram `700` no diretório `.ssh` e `600` no
`authorized_keys`. O endereço privado foi omitido da documentação pública.

O clone `~/pi-voice-ai` ainda não estava presente no Raspberry Pi. Isso foi
registrado como estado real, sem instalar pacotes ou iniciar a Fase 1.

Após validar a documentação, exclusões do Git, conteúdo staged e ausência de
credenciais, foi criado o commit inicial:

```text
chore: initialize PiVoice AI development environment
```

A branch `main` foi enviada para o remoto vazio e passou a acompanhar
`origin/main`. Não houve force push. A release `v0.1.0` foi autorizada depois da
apresentação dos resultados completos ao usuário.

## Fase 1 — Fundação da aplicação FastAPI

### Objetivo da aula

Criar um processo HTTP pequeno, testável e administrável pelo systemd. A aula separa
a disponibilidade do processo das integrações futuras: `/health` deve funcionar
mesmo sem OpenAI, microfone, STT ou TTS.

### Conceitos

FastAPI define a API; Uvicorn executa o servidor ASGI; pydantic-settings valida as
configurações do ambiente. Um virtual environment isola dependências Python. O
systemd mantém o processo ativo e envia sua saída ao journald. Logs em JSON deixam
cada evento estruturado para consulta posterior.

Arquitetura antes da aula:

```text
Windows --SSH--> Raspberry Pi sem aplicação
```

Arquitetura implementada localmente:

```text
Python -> Uvicorn -> FastAPI -> /health
                   |
                   +-> logs JSON
```

Arquitetura prevista após o deployment desta mesma fase:

```text
systemd -> .venv/bin/python -m app.main -> /health
                                      |
                                      +-> journald
```

### Implementação

`pyproject.toml` exige Python 3.11+ e fixa as dependências diretas observadas na
implementação. `app/config.py` lê somente host, porta e nível de log nesta fase;
valores futuros presentes no `.env` são ignorados. `app/api/health.py` retorna
somente `{"status":"ok"}`. O lifespan registra `APP_STARTED` e `APP_STOPPED`.

O serviço armazenado no repositório usa placeholders. `install_service.sh` os
substitui pelo usuário não-root e pelo caminho real do clone antes de instalar o
arquivo em `/etc/systemd/system`. Isso evita fixar um usuário específico no código.

O bootstrap consulta os pacotes antes de usar apt, cria o ambiente virtual e não
sobrescreve um `.env` existente. O deployment exige árvore Git limpa e usa
`git pull --ff-only`; depois executa compilação, pytest, instalação do serviço,
restart, health check, status e consulta de erros recentes.

### Comandos e testes realmente executados no Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall -q app
& 'C:\Program Files\Git\bin\bash.exe' -n scripts/bootstrap_pi.sh scripts/install_service.sh scripts/deploy.sh scripts/healthcheck.sh scripts/start.sh scripts/stop.sh scripts/restart.sh
.\.venv\Scripts\python.exe -m app.main
curl.exe --fail --silent --show-error http://127.0.0.1:8000/health
```

Resultado local: Python 3.12.0, um teste aprovado, compilação aprovada, sintaxe Bash
aprovada e resposta real `{"status":"ok"}`. O log de inicialização incluiu
`APP_STARTED`. Nenhum pedido OpenAI foi realizado.

Uma reinstalação dos metadados editable falhou inicialmente porque a restrição de
rede local bloqueou `files.pythonhosted.org`. O mesmo comando foi repetido com o
acesso de rede autorizado, instalou `pi-voice-ai 0.2.0.dev0` e o teste passou.
Isso mostrou também por que cada etapa deve conferir seu próprio código de saída.

### Segurança e configuração

O `.env` local existe, está ignorado, não está tracked nem staged. Seu conteúdo não
foi exibido. A chave OpenAI configurada pelo usuário não participa desta fase e não
é copiada ao Pi pelo Git. O template `.env.example` permanece sem credenciais.

### Resultado esperado no Raspberry Pi

Depois do deployment, `systemctl status pi-voice-ai` deve mostrar o serviço ativo,
`healthcheck.sh` deve retornar o JSON esperado e o journald deve conter logs JSON.
Esses resultados só serão marcados como reais depois da execução remota.

### Deployment remoto executado

O Pi não tinha o clone. Foi confirmado que o destino não existia antes de executar:

```bash
git clone https://github.com/crismoraes/pi-voice-ai.git "$HOME/pi-voice-ai"
cd "$HOME/pi-voice-ai"
./scripts/bootstrap_pi.sh
```

O clone apontou para `origin/main` no commit da fundação FastAPI. O bootstrap
informou que todos os pacotes do sistema já estavam disponíveis, atualizou o pip
dentro de `.venv`, instalou as dependências no ARM64 e criou `.env` a partir do
template com permissão `600`. Nenhuma credencial do Windows foi copiada.

No Raspberry Pi, Python 3.13 executou um teste com sucesso e `compileall` passou.
A aplicação temporária registrou `APP_STARTED` com versão `0.2.0.dev0`. Do Windows,
um pedido à porta 8000 do Pi recebeu `{"status":"ok"}`.

### Problemas reais do deployment

Uma tentativa de combinar `stat -c` com várias substituições em um comando SSH
teve as aspas interpretadas incorretamente. O pytest já havia passado, mas `stat`
falhou. A permissão foi então consultada com o formato simples `%a` e confirmou
`600`. Esse caso reforça que comandos remotos complexos devem ser pequenos ou
movidos para scripts versionados.

Ao enviar `Ctrl+C` para o teste temporário, a sessão SSH terminou e deixou o
processo Python escutando. Foi usado `ps` para identificar exatamente o PID e o
comando `.venv/bin/python -m app.main`; somente esse PID recebeu `SIGTERM`. Uma
consulta posterior confirmou a porta 8000 livre.

`sudo -n true` falhou, mostrando que o usuário exige senha para sudo. A senha não
foi solicitada nem transmitida. A etapa systemd ficou para execução interativa:

```powershell
ssh -t voicepi "cd ~/pi-voice-ai && ./scripts/deploy.sh"
```

Após o usuário digitar a senha no próprio terminal, o estado do serviço, health
check e logs foram inspecionados remotamente.

### Instalação systemd e condição de corrida do health check

O usuário executou `deploy.sh` interativamente. Bootstrap, reinstalação do pacote,
pytest, criação do link de inicialização e instalação da unidade systemd passaram.
O script falhou em seguida com `curl: (7)` porque consultou `127.0.0.1:8000` no
instante imediatamente posterior ao restart.

A inspeção remota mostrou que o serviço estava `enabled` e `active`, executando
`.venv/bin/python -m app.main`. Os logs continham `APP_STARTED`, conclusão do startup
e Uvicorn em `0.0.0.0:8000`. Uma nova consulta recebeu HTTP 200 e
`{"status":"ok"}`. Portanto, a aplicação não havia falhado; o check estava cedo.

`healthcheck.sh` foi corrigido para tentar até 20 vezes, com intervalo padrão de um
segundo. Ele termina imediatamente quando recebe o JSON esperado e ainda falha com
mensagem clara se o serviço não ficar pronto dentro do limite.

Depois do fast-forward no Pi, o novo health check passou na primeira tentativa. A
validação final mostrou `active/running`, `enabled`, usuário `cristiano`, status de
saída zero, nenhum restart e nenhuma entrada de prioridade erro no journald. O
endpoint também respondeu pela rede. A árvore Git do Pi ficou limpa e sincronizada.

A unidade está configurada para iniciar no boot. Não houve reboot real do Pi nesta
aula, portanto esse comportamento permanece configurado e inspecionado, sem teste
físico de reinicialização. Com essa limitação registrada, a Fase 1 foi concluída.

### Resultado da aula

O Raspberry Pi executa a fundação FastAPI como serviço systemd, reinicia o processo
em caso de falha, registra logs JSON no journald e expõe um endpoint de saúde que
não depende da OpenAI. Nenhuma funcionalidade de áudio foi iniciada.

## Fase 2 — WebRTC com loopback de áudio

### Objetivo da aula

Capturar o microfone no navegador, transportar áudio de forma segura até o Pi e
devolver a mesma faixa ao navegador. A meta é validar transporte e latência básica
antes de introduzir reconhecimento ou síntese de fala.

### Conceitos

WebRTC transporta mídia em tempo real. SDP descreve codecs e fluxos; ICE descobre
o caminho de rede; DTLS estabelece chaves; SRTP protege os pacotes de áudio. A API
HTTP troca a oferta e a resposta, mas o áudio segue diretamente pela conexão
WebRTC. `getUserMedia` exige HTTPS fora de `localhost`.

Arquitetura antes da aula:

```text
Browser --HTTP /health--> FastAPI
```

Arquitetura depois da implementação:

```text
Browser --HTTPS signaling--> FastAPI
   |                           |
   +----- WebRTC audio ------> aiortc
   <----- audio loopback -----+
```

### Implementação

Foi adicionado `aiortc 1.15.0`. Uma resolução sem instalação confirmou wheels
binários para Python 3.13 ARM64, incluindo PyAV, cryptography e pylibsrtp. Isso evita
compilar FFmpeg no Raspberry Pi nesta fase.

O gerenciador cria um `RTCPeerConnection` por oferta, registra eventos estruturados,
devolve a faixa de áudio recebida e fecha peers quando solicitado, em falha ou no
shutdown. A API expõe criação e remoção de peers. A página web solicita somente
áudio, negocia sem servidor STUN para o cenário LAN e reproduz a faixa retornada.

### HTTPS

Foi instalado `mkcert 1.4.4` pelo Windows Package Manager. Uma nova CA local foi
instalada no armazenamento confiável do Windows. O certificado de desenvolvimento
foi criado fora do repositório para o hostname local do Pi e expira em dezembro de
2028. Nenhum conteúdo de chave foi exibido ou documentado.

Uma primeira verificação de existência dos destinos TLS usou `Test-Path` com dois
parâmetros `-LiteralPath` na mesma expressão e gerou erro de binding. Como esse erro
não era terminante, o comando seguinte ainda criou os arquivos. A validação posterior
confirmou certificado e chave. Em scripts futuros, cada `Test-Path` deve ficar entre
parênteses e `$ErrorActionPreference` deve ser `Stop`.

### Testes executados

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -vv
.\.venv\Scripts\python.exe -m compileall -q app
```

Três testes passaram. O teste principal criou dois peers aiortc reais, negociou a
conexão e recebeu um frame de áudio devolvido pelo servidor. A sintaxe dos scripts
Bash e a compilação Python também passaram.

Depois do commit e push, o Pi atualizou `main` por fast-forward. O bootstrap baixou
os wheels ARM64 de PyAV, cryptography, SRTP e demais dependências sem compilar código
nativo. Em Python 3.13.5, os mesmos três testes passaram em 0,86 segundo e a árvore
Git permaneceu limpa.

O Uvicorn foi iniciado localmente em HTTPS na porta 8443 usando variáveis de
ambiente temporárias. O primeiro curl falhou com `CRYPT_E_NO_REVOCATION_CHECK`, pois
a CA local não publica uma lista de revogação acessível ao Schannel. A repetição
usou `--ssl-no-revoke`, que desativa apenas essa consulta; cadeia e hostname
continuaram validados. `/health` respondeu `{"status":"ok"}`. Não foi usado
`--insecure`, e a porta 8443 foi confirmada como livre após o teste.

Os arquivos TLS foram transferidos para o diretório privado do usuário no Pi. O
diretório recebeu modo `700`, a chave `600` e os certificados públicos `644`. A
comparação SHA-256 das chaves públicas derivadas confirmou que certificado e chave
privada formam o mesmo par. O `.env` foi atualizado sem exibir nem substituir a
chave OpenAI existente.

O primeiro health check HTTPS no Pi falhou porque consultava `127.0.0.1`, um nome
que não pertence ao certificado. O script foi corrigido para validar o hostname do
Pi e usar `curl --resolve` para direcioná-lo a `127.0.0.1`. Assim, a conexão continua
local e a verificação do nome permanece ativa. O teste corrigido passou na primeira
tentativa.

O teste real do deployment foi executado com:

```powershell
.\.venv\Scripts\python.exe scripts\live_webrtc_check.py `
  --url https://home-ai.local:8443 `
  --ca-file "$env:LOCALAPPDATA\mkcert\rootCA.pem"
```

Ele negociou ICE, DTLS e SRTP com o Pi, enviou áudio sintético, recebeu um frame
com amostras e removeu o peer. O journald registrou `WEBRTC_CONNECTED` e
`WEBRTC_DISCONNECTED`, sem avisos recentes. O serviço permaneceu ativo e habilitado.

### Resultado da aula

O teste físico foi realizado no navegador com microfone e saída de áudio reais. O
usuário permitiu o acesso ao microfone, iniciou o loopback e confirmou que ouviu a
própria voz retornando corretamente. Com o transporte automatizado, o ciclo de logs,
o HTTPS e a experiência acústica verificados, a Fase 2 foi concluída.

Os logs desse teste mostraram uma corrida no encerramento: a conexão já havia sido
removida pelo evento `closed` quando o navegador enviou `DELETE`, que respondeu
`404`. A operação foi tornada idempotente; encerrar novamente um peer ausente agora
responde `204`. O teste de integração passou a verificar as duas remoções.

## Fase 3 — reconhecimento de fala local

### Objetivo da aula

Transformar trechos do microfone do navegador em texto no Raspberry Pi, sem enviar
o áudio para a OpenAI. A aula introduz uma abstração substituível de STT, captura
manual de frases e medição do fator de tempo real.

### Conceitos

STT converte fala em texto. O Whisper Tiny usado nesta fase é multilíngue e roda
localmente em ONNX. Quantização int8 reduz tamanho e custo de inferência. O RTF é o
tempo de processamento dividido pela duração do áudio: valores abaixo de 1 indicam
processamento mais rápido que tempo real.

O VAD não faz parte desta etapa. O usuário marca manualmente o início e o fim da
frase, permitindo validar captura e reconhecimento antes de automatizar endpointing.

Arquitetura anterior:

```text
Microfone -> WebRTC -> Pi -> loopback
```

Arquitetura desta fase:

```text
Microfone -> WebRTC -> MediaRelay -> buffer mono 16 kHz -> STT local -> texto
                           |
                           +-> loopback opcional
```

### Implementação

Foi criada a interface `SpeechToText`, que recebe amostras `float32` e retorna texto,
duração, tempo de inferência e RTF. `SherpaWhisperSpeechToText` carrega o modelo
somente na primeira transcrição e executa a inferência com `asyncio.to_thread`. Um
lock impede duas decodificações simultâneas no mesmo reconhecedor.

O `MediaRelay` duplica a faixa WebRTC. O consumidor STT usa PyAV para converter o
áudio para mono em 16 kHz. O buffer aceita entre 0,5 e 30 segundos por frase e não é
gravado em disco. A interface web controla as APIs `transcription/start` e
`transcription/finish` e apresenta o resultado com suas métricas.

### Dependências e modelo

As versões usadas foram:

```text
sherpa-onnx 1.13.8
NumPy 2.4.6
Whisper Tiny multilíngue, encoder e decoder int8
```

O sherpa-onnx fornece wheels oficiais para Windows x64 e Linux ARM64. No Raspberry
Pi com Python 3.13, os wheels foram instalados sem compilação. O modelo oficial foi
baixado com:

```bash
./scripts/download_stt_model.sh
```

O arquivo compactado tinha cerca de 110 MB; o diretório extraído ocupou 245 MB. O
checksum SHA-256 observado foi incorporado ao script, que valida o download e não
repete a instalação quando os três arquivos int8 necessários já existem.

### Configuração

```text
STT_ENGINE=sherpa-whisper
STT_MODEL_DIR=models/sherpa-onnx-whisper-tiny
STT_LANGUAGE=pt
STT_NUM_THREADS=4
STT_MIN_AUDIO_SECONDS=0.5
STT_MAX_AUDIO_SECONDS=30
```

O `.env` remoto foi atualizado sem exibir ou alterar a chave OpenAI existente. O
valor histórico `STT_ENGINE=sherpa` continua aceito como alias para não quebrar
instalações anteriores.

### Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
node --check web\app.js
```

Seis testes passaram no Windows. O teste de integração cria peers WebRTC reais,
captura áudio reamostrado, usa um STT falso determinístico e verifica o texto e as
métricas retornadas. Os mesmos seis testes passaram no Pi ARM64.

O benchmark do modelo real usa:

```bash
.venv/bin/python scripts/benchmark_stt.py arquivo.wav
```

As três amostras fornecidas com o modelo são inglesas. Quando executadas com idioma
forçado para português, mediram RTF entre 0,203 e 0,225, mas produziram texto sem
valor para qualidade. Ao repetir `0.wav` com `STT_LANGUAGE=en`, o texto correspondeu
à referência e o Pi processou 6,625 s de áudio em 1,134 s, RTF 0,171.

### Problemas encontrados

O `.env` local ainda continha `STT_ENGINE=sherpa`, o que inicialmente interrompeu a
coleta dos testes. A implementação passou a aceitar esse nome antigo como alias.

O utilitário `/usr/bin/time` não estava instalado no Pi. Não foi adicionado um pacote
somente para o benchmark; as métricas internas do reconhecedor foram usadas.

Após a mudança de IP, o alias `voicepi` ainda apontava para o endereço anterior. O
novo host foi localizado por mDNS e validado primeiro pelo certificado HTTPS já
confiável antes de registrar sua chave SSH. Mais tarde, o mDNS e o novo endereço
ficaram temporariamente indisponíveis. Quando o Pi voltou à rede, o alias `voicepi`
foi alterado para `home-ai.local` e voltou a funcionar sem depender do endereço
concedido por DHCP.

Na primeira execução de `live_stt_check.py`, o `httpx` herdou a configuração de
proxy do Windows e não alcançou a rede local. O cliente passou a usar
`trust_env=False`. Na segunda, a duração do PyAV foi multiplicada pela base de tempo
em vez de dividida, causando uma espera excessiva; o cálculo foi corrigido e ganhou
um teste de regressão.

### Resultado atual

O código, as dependências, o modelo, os testes ARM64, o benchmark e o serviço
`0.3.0` foram implantados. O teste ao vivo enviou um WAV do Windows ao Pi por
WebRTC, capturou 6,539 s e concluiu a inferência em 1,147 s, RTF 0,175. O health
check respondeu, o serviço permaneceu ativo e os logs não mostraram erros.

O usuário realizou várias transcrições físicas pelo navegador em português. A última
foi uma fala longa sobre o teste de um novo sistema no Raspberry Pi 5 e sobre as
próximas etapas. O Pi processou 18,06 s de áudio em 3,346 s, RTF 0,185. O resultado
preservou o assunto e a sequência da mensagem, embora tenha trocado algumas
palavras. Esse nível confirmou o funcionamento de ponta a ponta e também registrou
a limitação de qualidade do Whisper Tiny. A Fase 3 foi
concluída no marco `v0.3.0`.

## Fase 4 — resposta textual com OpenAI

### Objetivo da aula

Enviar à OpenAI somente o texto produzido pelo STT local e mostrar a resposta no
navegador enquanto ela é gerada. O áudio continua restrito ao navegador e ao
Raspberry Pi.

### Arquitetura

```text
Voz -> WebRTC -> STT local -> transcrição -> OpenAI Responses API
                                              |
Interface web <- SSE com deltas de texto <-----+
```

Foi criada a abstração `LanguageModel` e o adaptador
`OpenAIResponsesLanguageModel`. O endpoint `POST /api/assistant/responses` recebe
até 4.000 caracteres e devolve eventos `delta`, `done` ou `error`. O evento final
contém o modelo, o tempo até o primeiro texto e o tempo total.

A chave é lida de `OPENAI_API_KEY` somente no servidor. O navegador não recebe essa
credencial. O conteúdo do prompt e da resposta também não aparece nos logs; somente
modelo, quantidade de caracteres e tempos são registrados. As requisições usam
`store=false`, limite padrão de 300 tokens e um lock para evitar geração simultânea.

O modelo padrão é `gpt-6-luna`, configurável no `.env`. A implementação usa o SDK
oficial `openai 3.19.2` e a Responses API recomendada pela documentação oficial para
novas integrações de texto e streaming.

### Validação local inicial

Nove testes passaram no Windows. Eles cobrem a extração dos eventos de texto do SDK,
a ausência de chave, o streaming SSE, o WebRTC, o STT e o health check. Uma chamada
real mínima usando a chave do `.env` retornou a frase solicitada por streaming. A
implantação ARM64 e o fluxo físico completo ainda precisam ser demonstrados.
