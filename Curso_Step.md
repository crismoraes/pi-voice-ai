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

### Implantação inicial no Raspberry Pi

A chave foi transferida separadamente por entrada padrão do SSH, sem imprimir seu
valor e sem copiar o `.env` inteiro. O SDK instalou wheels compatíveis com Python
3.13 ARM64, incluindo `jiter`, sem compilação nativa. Os nove testes passaram no Pi.

Depois do restart, o serviço `0.4.0.dev0` respondeu ao health check HTTPS. O script
`live_llm_check.py` enviou uma frase ao endpoint implantado e recebeu a resposta do
`gpt-6-luna` por streaming. O primeiro texto chegou em 1,520 s e a resposta terminou
em 1,683 s. O journald registrou início, primeiro token e conclusão, sem registrar o
conteúdo e sem erros. Falta o teste físico que une microfone, STT e resposta textual
na interface do navegador.

### Validação física e conclusão

O usuário perguntou por voz quem chegou ao Brasil. A captura teve 7,08 s e o STT
local terminou em 0,98 s, RTF 0,14. A transcrição trocou uma palavra, mas preservou
a intenção. O `gpt-6-luna` interpretou corretamente a pergunta, respondeu Pedro
Álvares Cabral e acrescentou o contexto dos povos indígenas já presentes no
território. O primeiro texto apareceu em 1,97 s e a resposta terminou em 2,85 s.

A resposta trouxe marcação Markdown para destacar um nome. Como a interface usa
texto simples e uma fase posterior enviará a saída ao TTS, a instrução padrão passou
a pedir respostas sem Markdown. Com o caminho voz, STT local, OpenAI e streaming de
texto comprovado, a Fase 4 foi concluída no marco `v0.4.0`.

A checagem final da versão instalada confirmou `APP_STARTED` em `0.4.0`, health
check aprovado e resposta sem Markdown. O primeiro texto chegou em 2,216 s e o fluxo
terminou em 2,393 s.

## Fase 5 — voz local com Piper e WebRTC

### Objetivo da aula

Converter a resposta textual do assistente em fala no Raspberry Pi e entregá-la ao
alto-falante do navegador pela conexão WebRTC que já transporta o microfone.
Nenhum áudio é enviado à OpenAI.

### Decisão técnica

Foi escolhida a voz brasileira `vits-piper-pt_BR-jeff-medium` por funcionar com o
`sherpa-onnx 1.13.8` já usado no STT e oferecer wheel ARM64. O pacote tem cerca de
64 MB compactado, ocupa 82 MB e produz PCM mono em 22.050 Hz. O script
`download_tts_model.sh` baixa a distribuição oficial, confere o SHA-256 e não repete
o trabalho quando modelo, tokens e dados do eSpeak já existem.

O contrato `TextToSpeech` recebe texto e devolve amostras `float32`, taxa de
amostragem e tempo de processamento. `SherpaPiperTextToSpeech` carrega o modelo na
primeira solicitação e executa inferência fora do event loop, protegida por lock.

### Transporte de saída

`AssistantAudioTrack` mantém uma única faixa WebRTC de saída. A cada frame recebido
do microfone, ela envia uma destas fontes:

1. voz sintetizada que estiver na fila;
2. microfone, quando o loopback de diagnóstico estiver habilitado;
3. silêncio, durante a espera.

As amostras do Piper são convertidas de 22.050 para 48.000 Hz pelo PyAV antes do
envio. O endpoint `POST /api/webrtc/peers/{peer_id}/speech` sintetiza a resposta e
informa duração, processamento, RTF e taxa original. O endpoint `PUT
/api/webrtc/peers/{peer_id}/loopback` separa a preferência do navegador do volume da
faixa, permitindo que a resposta TTS seja ouvida mesmo com loopback desabilitado.

### Configuração e instalação

```text
TTS_ENGINE=sherpa-piper
TTS_MODEL_DIR=models/vits-piper-pt_BR-jeff-medium
TTS_NUM_THREADS=2
TTS_SPEED=1.0
TTS_MAX_TEXT_CHARACTERS=2000
```

```bash
./scripts/download_tts_model.sh
.venv/bin/python scripts/benchmark_tts.py \
  "Olá. Este é o teste da voz local do PiVoice AI." \
  --output /tmp/pi-voice-ai-tts.wav
```

O primeiro benchmark real no Raspberry Pi gerou 3,036 s de áudio em 0,707 s, com
RTF `0,233`. O WAV resultante foi confirmado como PCM mono, 16 bits, 22.050 Hz.

### Testes e implantação

Onze testes passaram no Windows e no Pi. O teste de integração usa dois peers reais,
um sintetizador determinístico e verifica que amostras não silenciosas atravessam
ICE, DTLS, SRTP e Opus. O teste ao vivo pode ser repetido no Windows:

```powershell
.\.venv\Scripts\python.exe scripts\live_tts_check.py `
  --url https://home-ai.local:8443 `
  --ca-file "$env:LOCALAPPDATA\mkcert\rootCA.pem" `
  --text "Olá. A voz local está funcionando."
```

Na implantação, uma frase de 70 caracteres gerou 3,882 s de voz em 0,795 s, RTF
`0,205`. O peer Windows recebeu 185 frames audíveis, com pico PCM 14.816. Os logs
mostraram `WEBRTC_CONNECTED`, `TTS_STARTED`, `TTS_COMPLETED` e cleanup sem erro.

### Problemas encontrados e estado

O teste de integração inicialmente examinou apenas os dez primeiros frames depois
da síntese. Eles ainda pertenciam ao silêncio acumulado enquanto o STT era testado.
O teste passou a drenar até dois segundos de buffer e comprovou o áudio TTS.

A primeira execução do verificador ao vivo não abriu a porta da rede local dentro
do ambiente restrito, embora DNS, SSH, serviço e porta estivessem corretos. Repetir
o mesmo comando com acesso autorizado à rede local confirmou o transporte; nenhuma
mudança no Pi foi necessária.

Código, modelo, testes ARM64, benchmark e transporte ao vivo foram implantados. No
teste físico, o usuário perguntou qual é a capital dos Estados Unidos. Os 5,50 s de
fala foram transcritos em 0,79 s, RTF `0,14`. O modelo respondeu corretamente
Washington, D.C.; o primeiro texto apareceu em 0,97 s e terminou em 1,13 s. O Pi
gerou 2,79 s de voz em 0,56 s, RTF `0,20`, e o navegador reproduziu a resposta.
Esse teste encerrou a Fase 5 no marco `v0.5.0`.

## Fase 6 — conversa automática e contexto

### Objetivo da aula

Retirar o botão de finalização do caminho principal. O microfone permanece aberto,
o Raspberry Pi identifica uma frase completa pelo silêncio e executa STT, LLM e TTS.
Perguntas posteriores recebem o histórico recente da mesma sessão.

### VAD local

Foi escolhido o `silero_vad.onnx` oficial suportado pelo sherpa-onnx. O detector usa
16 kHz, janela de 512 amostras, limiar `0,5`, fala mínima de 0,3 s e silêncio final
de 0,8 s. O arquivo observado tinha 643.854 bytes e SHA-256
`9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`.

```bash
./scripts/download_vad_model.sh
```

O script é idempotente: aceita o arquivo existente somente quando o checksum passa.
O bootstrap agora instala STT, TTS e VAD sem armazenar modelos no Git.

### Orquestração independente do transporte

`ConversationManager` recebe as abstrações `SpeechToText`, `LanguageModel` e
`TextToSpeech`. Cada peer possui histórico e lock próprios. Um turno emite:

```text
speech_started -> speech_ended -> transcribing -> transcript
-> assistant_delta(s) -> assistant_done -> tts_done -> ready
```

O navegador acompanha os eventos por SSE e continua recebendo o áudio pelo WebRTC.
A fila de eventos é limitada; se o cliente parar de consumir, os eventos antigos são
descartados sem bloquear áudio ou inferência. O histórico conserva no máximo seis
pares e é apagado ao fechar o peer. Prompts, transcrições e respostas não são logs.

### Compatibilidade com o modo manual

A caixa **Conversa automática** vem marcada. Ao desmarcá-la, os endpoints manuais de
captura, streaming textual e síntese da Fase 5 continuam disponíveis. O loopback de
diagnóstico também permanece separado.

Enquanto um turno é processado e reproduzido, a entrada do VAD é pausada. Isso evita
realimentação da voz do assistente. A interrupção intencional, chamada barge-in, é o
objetivo da Fase 7 e ainda não está ativa.

### Validação inicial

Quatorze testes passaram no Windows e no Raspberry Pi. O teste de integração usa
dois peers WebRTC, um VAD determinístico e adaptadores falsos para comprovar toda a
sequência automática. Outro teste executa duas rodadas no gerenciador e verifica que
o segundo pedido recebe o primeiro par de mensagens.

O Silero real carregou no Windows e segmentou uma pergunta portuguesa sintetizada.
Na implantação `0.6.0.dev0`, um teste de dois turnos produziu quatro mensagens de
histórico ao final. O segundo LLM recebeu `history_messages: 2`, confirmando o uso
do primeiro turno. As duas respostas chegaram pelo WebRTC; o Windows observou 463
frames audíveis e pico PCM 14.223. Não houve erro no journald.

O Whisper Tiny teve erros nas frases sintetizadas, mas o segundo modelo respondeu
usando exatamente o conteúdo que havia sido reconhecido no primeiro turno. Isso
separa a validação da memória da avaliação de qualidade do STT.

### Validação física e encerramento

No navegador, duas falas de 5,00 s e 5,39 s foram encerradas automaticamente pelo
silêncio, sem clicar em finalizar. O STT levou 0,95 s e 1,03 s, com RTF `0,19` nos
dois casos. O primeiro texto apareceu em 1,32 s e 0,94 s; a síntese local levou
0,34 s em ambos, produzindo 1,74 s e 1,92 s de áudio com RTF `0,20` e `0,18`.

Os logs do mesmo peer registraram `history_messages: 4` antes do primeiro turno
relatado, seis depois dele, oito depois do segundo e, após mais duas interações, o
limite de 12 mensagens. Todos os turnos terminaram com `CONVERSATION_TURN_COMPLETED`,
o peer fechou normalmente e o serviço permaneceu ativo, sem erros. As palavras
incomuns foram transcritas de formas diferentes pelo Whisper Tiny; as respostas
usaram coerentemente o texto reconhecido. Com isso, a Fase 6 foi concluída e
publicada como `v0.6.0`.

## Fase 7 — barge-in

### Objetivo da aula

Permitir que o usuário interrompa o assistente apenas começando a falar. O VAD passa
a receber o microfone também durante o processamento e a reprodução da resposta.
Quando encontra uma nova fala, o servidor cancela a tarefa corrente, esvazia o áudio
do assistente e usa o mesmo segmento para iniciar o próximo turno.

O evento SSE `interrupted` informa se a interrupção ocorreu em `processing` ou
`playback` e quantos segundos de áudio enfileirado foram descartados. O cliente exibe
essa mudança imediatamente. `ENABLE_BARGE_IN` permite desativar o comportamento sem
alterar o restante do pipeline.

A validação unitária usa uma resposta de cinco segundos, inicia nova fala durante
`playback`, confirma o cancelamento e verifica que o segundo turno chega ao estado
`ready`. Quinze testes passaram no Windows e no Raspberry Pi.

No teste WebRTC implantado, o primeiro áudio gerou 2,453 s de resposta falada. A
segunda fala foi detectada durante a reprodução e removeu os 1,573 s restantes. O
novo turno terminou normalmente, gerou 2,436 s de voz e o Windows recebeu 140 frames
audíveis. O serviço permaneceu ativo e não houve erro nessa execução.

Na validação física, o usuário perguntou sobre Moisés e interrompeu a resposta para
pedir informações sobre Jesus. O servidor removeu 28,194 s dos 36,351 s de áudio da
primeira resposta. A nova fala teve 2,54 s, STT de 0,60 s, primeiro texto em 1,60 s,
resposta textual em 2,48 s e 23,61 s de voz sintetizados em 4,67 s, RTF `0,20`.

Duas chamadas anteriores da OpenAI terminaram sem texto. O pipeline passou a repetir
uma única vez somente nesse caso, mantendo os erros explícitos se a repetição também
vier vazia. Dezesseis testes passaram nos dois ambientes. A validação encerrou a
Fase 7 no marco `v0.7.0`.

## Fase 8 — otimização orientada por medições

### Linha de base

O Pi 5 possui quatro Cortex-A76, 8 GiB de RAM, temperatura inicial de 41,7 °C e
`throttled=0x0`. Foram executadas três rodadas com uma a quatro threads. Para um WAV
de 1,467 s, o Whisper Tiny INT8 teve medianas de 0,496 s, 0,352 s, 0,324 s e 0,327 s.
No TTS curto, as medianas foram 0,344 s, 0,218 s, 0,182 s e 0,176 s. Três threads
oferecem desempenho próximo do melhor e deixam um núcleo para WebRTC e VAD.

### Primeiras mudanças

O adaptador Whisper passou a localizar os arquivos Tiny ou Base e selecionar INT8 ou
FP32 por configuração. A captura WebRTC usa `MediaRelay` sem buffering intermediário.
No caminho de saída, o texto é separado por sentenças; o primeiro áudio é enfileirado
assim que o primeiro trecho fica pronto, em paralelo temporal com a síntese restante.
O evento `tts_chunk` atualiza a interface no primeiro trecho.

O Whisper Base oficial foi baixado somente para benchmark. O Tiny ocupa 245 MiB e o
Base 433 MiB no Pi. A seleção final depende da comparação de latência e transcrição.

### Seleção baseada nos resultados

Com três threads e o mesmo WAV de 1,467 s, as medianas Tiny INT8, Tiny FP32, Base
INT8 e Base FP32 foram 0,325 s, 0,426 s, 0,719 s e 0,969 s. O Base também produziu
mais erros nesse corpus curto. O serviço manteve Tiny INT8 e o Base temporário foi
removido após liberar 433 MiB.

O benchmark de TTS comparou limites de 80, 120, 180, 240 e 400 caracteres. Como o
divisor prioriza finais de sentença, 240 caracteres produziu três partes, primeiro
áudio mediano de aproximadamente 0,605 s e processamento total de 2,449 s. Limites
de 80 e 120 criaram quatro partes e elevaram o total sem antecipar a primeira frase.

No WebRTC real, dois turnos aquecidos iniciaram voz em 0,257 s e 0,362 s; o segundo
precisou de 0,874 s para sintetizar todo o áudio, comprovando a sobreposição. STT e
TTS passaram a carregar em paralelo durante a inicialização. Depois do reinício, os
modelos ficaram prontos em cerca de 1,41 s e o primeiro turno entregou voz em 0,586 s,
contra 1,652 s antes do pré-carregamento. Dezessete testes passaram nos dois ambientes.

### Validação física e conclusão

No navegador, uma fala de 3,31 s foi transcrita em 0,55 s, RTF `0,17`. O primeiro
texto apareceu em 0,95 s e a resposta textual terminou em 2,49 s. Seus 802 caracteres
foram divididos em 12 trechos, que produziram 43,75 s de voz. O primeiro áudio ficou
disponível em 0,462 s, embora a síntese completa tenha levado 7,323 s, demonstrando
que a reprodução e a geração ocorreram ao mesmo tempo. A história foi ouvida com
continuidade, o serviço permaneceu ativo e os logs do turno não mostraram erros.
Essa validação encerrou a Fase 8 no marco `v0.8.0`.

## Fase 9 — microfone e alto-falante USB

### Inventário do hardware

Com os dois conectores de áudio ligados à mesma interface USB, `lsusb` identificou
o dispositivo P10S. `arecord -l` encontrou captura e `aplay -l` encontrou reprodução
na mesma placa. O nome ALSA `plughw:CARD=P10S,DEV=0` foi escolhido no lugar de
`hw:2,0`: `plughw` faz as conversões necessárias e `CARD=P10S` permanece legível
mesmo se o índice numérico mudar.

O teste de captura confirmou PCM `S16_LE`, mono e 16 kHz. O usuário `cristiano`, que
executa o serviço systemd, já pertence ao grupo `audio`. Portanto, não foi necessário
alterar permissões nem executar a aplicação como root.

### Arquitetura do adaptador

`arecord` entrega blocos PCM de 512 amostras ao Silero VAD. Um segmento concluído
segue pelo mesmo `ConversationManager`, Whisper local, OpenAI e Piper já validados.
Na saída, todos os trechos TTS do turno são escritos em um único processo `aplay`,
permitindo que o alto-falante comece antes do fim da síntese.

Antes de abrir o microfone, o adaptador usa `amixer` para restaurar os níveis
configurados de reprodução e captura. Isso transforma a correção aplicada durante o
troubleshooting em comportamento reproduzível após reinícios ou resets da interface.
Como o modo USB não possui uma tela obrigatória, uma falha do turno também gera um
aviso falado local. A mensagem pode ser alterada por `USB_ERROR_MESSAGE`.

O modo é selecionado no `.env` por `AUDIO_MODE=usb`. Os dispositivos de entrada e
saída têm configurações separadas, então uma fase futura pode usar interfaces USB
distintas sem alterar VAD, STT, LLM, TTS ou histórico. O modo WebRTC continua
disponível ao restaurar `AUDIO_MODE=webrtc`.

O barge-in local começa desligado. Sem cancelamento acústico de eco, o microfone
pode interpretar a voz do próprio alto-falante como uma nova fala. Primeiro serão
validados o fluxo completo, o volume e a distância física; depois a interrupção USB
poderá ser habilitada conscientemente.

### Primeira validação física USB

Depois de recuperar a interface P10S, o usuário falou no microfone e ouviu a resposta
no alto-falante USB. No último turno observado, o VAD encerrou 3,244 s de fala e o
Whisper terminou em 0,540 s, RTF `0,167`. O modelo iniciou texto em 4,814 s após uma
resposta vazia e sua repetição automática. A voz começou a ser enfileirada em 0,191 s.
O Piper produziu 18,472 s de áudio em cinco trechos, com 3,075 s de síntese e RTF
`0,166`. A reprodução terminou normalmente, o adaptador voltou ao estado pronto e
o serviço permaneceu ativo.

### Decisão de lançamento

O marco `v0.9.0` mantém `USB_ENABLE_BARGE_IN=false` como padrão. O recurso continua
disponível para ambientes que controlam eco, mas a instalação básica prioriza não
confundir a própria voz do alto-falante com uma nova pergunta. O barge-in WebRTC
permanece habilitado e não é afetado por essa escolha. Com captura, conversa, voz,
níveis de mixer, recuperação de falha e documentação validados, a Fase 9 foi concluída.

## Fase 10 — medindo tokens e estimando custos

O evento final do streaming da Responses API contém o uso calculado pelo provedor.
A aplicação captura essas contagens no servidor e associa cada chamada à duração e
latência do turno. Isso demonstra que o custo inclui instruções e histórico da
conversa, além da frase atual.

O exercício da aula cria um banco SQLite local com dados numéricos e uma página em
`/dashboard.html`. O aluno compara entrada, cache, saída, total e custo por fala,
além dos acumulados de 7, 30, 90 ou 365 dias. O projeto não grava áudio, transcrição
ou resposta. A tabela de preços fica configurável porque tarifas e aliases podem
mudar, e o dashboard chama o valor monetário de estimativa.

### Evolução visual de Recent turns

A primeira versão colocou 14 colunas em uma tabela. Em telas menores que a soma das
colunas, custo e tempo ficavam fora da área visível, enquanto a única barra horizontal
aparecia depois de até cem registros. Para consultar o custo de uma fala, era preciso
descer, mover a barra e voltar ao registro.

A interface passou a representar cada turno como um cartão responsivo. O cabeçalho
mantém data, origem, pipeline e custo juntos. Uma grade mostra STT, LLM e TTS/voz; a
grade seguinte mostra tokens e tempo. Em larguras menores, as grades quebram para
quatro ou duas colunas. A informação permanece a mesma e nenhuma rolagem lateral é
necessária. Esse caso é útil no curso para mostrar que observabilidade também exige
uma apresentação que permita comparar os dados sem esforço mecânico.

Fluxo ensinado:

```text
Fala -> STT local -> Responses API -> response.completed.usage
                                      |
                                      v
                              SQLite local -> dashboard
```

A documentação oficial descreve os campos de uso na
[Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
e publica a [tabela de preços](https://developers.openai.com/api/docs/pricing?tab=suite).

### Preparação do sistema estável

O teste físico posterior mostrou uma decisão diferente do benchmark curto da Fase
8: o Whisper Small INT8 entendeu o português com muito mais consistência, embora
leve alguns segundos a mais. Por isso, a reconstrução da Fase 10 usa Small como
padrão, três threads e `VAD_MIN_SILENCE_SECONDS=1.0`. O bootstrap lê o caminho
configurado no `.env`, escolhe `tiny` ou `small` e verifica o SHA-256 do pacote.

O áudio USB também ganhou supervisão. O serviço reabre `arecord` quando o processo
termina ou quando chegam somente amostras PCM de valor zero por dez segundos. Esse
caso é diferente de silêncio acústico: mesmo uma sala silenciosa normalmente tem
ruído de fundo no conversor. Se a interface USB inteira ficar travada, o reset
seletivo documentado no troubleshooting continua sendo a recuperação final.

Para coletar uma visão sanitizada do sistema em uma aula ou atendimento remoto:

```bash
./scripts/diagnose_pi.sh
```

O script não lê `.env`. Ele mostra systemd, endpoints, ALSA, memória, disco,
temperatura, throttling e avisos recentes.

### Validação remota da inicialização e recuperação

Os 24 testes passaram no Pi. Para validar o supervisor sem desconectar o hardware,
o processo `arecord` foi encerrado uma vez de forma controlada. O journal registrou
`USB_CAPTURE_RETRY_SCHEDULED`, restaurou o mixer e registrou
`USB_CAPTURE_RESTARTED` após três segundos, com um novo PID e o serviço ainda ativo.

Depois de um reboot real, o SSH voltou na terceira tentativa da verificação remota.
O diagnóstico confirmou `active/running`, unidade habilitada, `NRestarts=0`,
`ExecMainStatus=0`, P10S disponível para captura e reprodução e `arecord` aberto.
Health, dashboard e API de consumo responderam; `data/usage.db` estava em modo
`0600`. O Pi tinha 6,6 GiB disponíveis, temperatura de 45 °C, `throttled=0x0` e
nenhum erro no journal desse boot. Na última verificação, o usuário falou pelo
microfone USB, recebeu a resposta no alto-falante e confirmou que funcionou
perfeitamente. Essa demonstração concluiu a Fase 10 no marco `v1.0.0`.

## Pós-1.0 — alternando entre OpenAI e um LLM local

### Controle On/Off para desenvolvimento e testes

Deixar o assistente USB ativo durante programação pode fazer o VAD interpretar
conversas do ambiente, iniciar o LLM e consumir tokens. O dashboard recebeu uma
chave global **Voice assistant**. Desligar não muda nem descarrega o modelo
selecionado: interrompe o turno atual, fecha a captura USB e bloqueia novas
requisições de voz antes do VAD, STT e LLM. No WebRTC, a conexão pode permanecer
aberta, mas recebe o evento `paused` e deixa de iniciar turnos automáticos.

```text
On  -> microfone -> VAD -> STT -> LLM -> TTS
Off -> captura fechada/ignorada -> zero novos tokens
```

A API usada pelo dashboard é `PUT /api/system/assistant` com o booleano `enabled`.
O arquivo ignorado `data/assistant-state.json` usa gravação atômica e permissão
`0600`; assim, um reboot não volta a ligar silenciosamente o microfone. O `.env`
define somente o primeiro estado com `ASSISTANT_ENABLED=true`. Esta separação é
útil no curso: escolher o provedor e permitir captação são decisões independentes.

### Objetivo da aula

Executar o Qwen3.5 2B Q4_K_M no Raspberry Pi 5 com llama.cpp e permitir que o aluno
troque de provedor no dashboard sem editar `.env` nem reiniciar a aplicação.

### Por que llama.cpp e Q4_K_M

llama.cpp oferece um servidor HTTP com streaming e endpoints compatíveis com o
formato OpenAI. A compilação nativa ARM64 usa as instruções do Raspberry Pi. A
quantização Q4_K_M reduz o Qwen3.5 2B para cerca de 1,28 GB, deixando espaço na
memória de 8 GB para Whisper Small, Piper, VAD e o sistema operacional. O modelo
2B prioriza qualidade em português dentro desse limite; o benchmark físico ainda
deve medir tokens por segundo, primeiro texto, temperatura e qualidade das respostas.

### Arquitetura implementada

```text
microfone -> VAD -> Whisper -> LanguageModelSelector
                                |-> OpenAI: gpt-6-luna
                                +-> llama.cpp: Qwen3.5 2B Q4_K_M
                                                     |
alto-falante <- Piper <- texto em streaming ----------+
```

O servidor local escuta somente em `127.0.0.1:8081`. A interface envia
`PUT /api/system/llm` com um provedor e modelo presentes na lista permitida. Antes
da troca local, o backend consulta `/health`. A gravação atômica em
`data/llm-selection.json` preserva a escolha após reinícios. Uma trava mantém cada
resposta inteira no mesmo provedor caso alguém clique em **Apply LLM** durante um
turno.

O modo de raciocínio do Qwen fica desativado para conversa por voz. Isso evita
tokens internos e reduz o tempo até a resposta. O dashboard mostra provedor,
modelo, execução local ou em nuvem e a taxa de tokens por segundo informada pelo
llama.cpp depois de uma geração. Todo o texto do dashboard foi mantido em inglês.

### Instalação reproduzível

```bash
./scripts/bootstrap_pi.sh
sudo ./scripts/install_service.sh
sudo systemctl restart pi-voice-ai-llm.service pi-voice-ai.service
curl --fail http://127.0.0.1:8081/health
.venv/bin/python scripts/benchmark_local_llm.py
```

O instalador fixa o llama.cpp em `v0.5.0`, revisão
`d2e54583c7452353eb35d40431281f6ee984332f`, e valida o GGUF com SHA-256
`aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`.
O arquivo fica em `models/`, e a árvore compilada em `vendor/`; ambos são ignorados
pelo Git. O arquivo multimodal `mmproj` não é necessário para esta aplicação de
texto e voz.

### Validação da aula

Antes de considerar a melhoria concluída, confirme os testes Python e Bash, os dois
serviços ativos, o endpoint local, uma resposta direta do llama.cpp, uma troca pelo
dashboard e uma conversa física. Registre primeiro texto, tempo total, tokens/s,
RAM, temperatura e throttling. Compare depois com OpenAI usando a mesma pergunta.

Na execução real, a compilação detectou Cortex-A76, ARM `dotprod`, FP16 vetorial e
OpenMP. O download de 1.280.835.840 bytes passou no SHA-256. Os 29 testes passaram
no Pi. O benchmark retornou uma explicação correta em português com primeiro texto
em 1,221 s, conclusão em 8,539 s e 6,01 tokens/s. Uma pergunta curta pelo endpoint
da aplicação começou em 1,495 s e terminou em 2,626 s. A troca funcionou nos dois
sentidos e a escolha local sobreviveu ao reinício da aplicação.

O registro de consumo confirmou 48 tokens de entrada, 8 de saída, 56 no total e
nenhum custo de nuvem. `pi-voice-ai.service` e `pi-voice-ai-llm.service` permaneceram
ativos, com zero reinícios e nenhum erro recente. O `llama-server` estava ligado
somente a `127.0.0.1:8081`. Durante a verificação havia 5,3 GiB de RAM disponível,
temperatura de 46,6 °C, swap sem uso e `throttled=0x0`. A validação física seguinte
confirmou perguntas consecutivas pelo microfone e respostas no alto-falante depois
da correção que serializa a captura e a reprodução da P10S.

## Fase 11 — seleção de STT e TTS

### Objetivo da aula

Permitir que o aluno compare qualidade, latência e consumo de memória sem editar o
`.env` ou reiniciar o serviço. O dashboard continuará em inglês e terá três linhas
independentes: LLM provider/model, STT provider/model e TTS provider/model.

O Pi já possui os seguintes candidatos:

```text
STT / Local (sherpa-onnx)
  - Whisper Small INT8  -> qualidade atual em português
  - Whisper Tiny INT8   -> menor latência e menor uso de memória

TTS / Local (sherpa-onnx)
  - Piper pt_BR Jeff Medium
```

Mesmo havendo somente uma voz TTS agora, o combobox nasce com o mesmo contrato dos
demais. Assim, adicionar outra voz Piper ou um provedor de nuvem exigirá apenas
registrar uma opção allowlisted.

### Contrato planejado

`GET /api/system/info` continua sanitizado e acrescenta `provider`, `options` e
`available` a STT e TTS. As escritas são:

```http
PUT /api/system/stt
Content-Type: application/json

{"provider":"sherpa-onnx","model":"whisper-tiny-int8"}
```

```http
PUT /api/system/tts
Content-Type: application/json

{"provider":"sherpa-onnx","model":"pt_BR-jeff-medium"}
```

Os arquivos `data/stt-selection.json` e `data/tts-selection.json` são atômicos,
ignorados pelo Git e gravados como `0600`. A API aceita somente nomes conhecidos;
caminhos de modelo nunca virão do navegador.

### Troca segura em runtime

A trava `pipeline_selection_lock` cobre o turno completo no `ConversationManager`.
Uma alteração aguarda o turno que já está usando o modelo, carrega e aquece o
candidato, persiste a seleção e só então descarta o adaptador anterior. Se o warm-up
falhar, a API responde `503` e o modelo atual continua ativo. Esse fluxo evita
misturar duas vozes entre trechos do mesmo TTS e evita acumular modelos grandes na
RAM do Raspberry Pi.

`SpeechToTextSelector` e `TextToSpeechSelector` implementam os contratos que já eram
usados por WebRTC, USB e `ConversationManager`. Assim, os transportes não precisam
conhecer o modelo escolhido. O dashboard usa **Apply STT** e **Apply TTS**, apresenta
nomes amigáveis e desabilita candidatos que não estão instalados.

### Critérios de aceitação

1. Trocar Small para Tiny e voltar para Small pelo dashboard.
2. Confirmar persistência após restart do serviço.
3. Simular modelo ausente e comprovar rollback sem interromper o assistente.
4. Fazer uma conversa física com cada STT e registrar RTF, qualidade, RAM e temperatura.
5. Aplicar TTS durante uma conversa longa e comprovar que a voz muda apenas no turno seguinte.
6. Confirmar que `/api/system/info` não revela caminhos nem credenciais.

Na implementação inicial, 40 testes passaram no Windows e no Raspberry Pi ARM64.
Eles cobrem persistência, allowlist, rollback, disponibilidade, endpoints
sanitizados e a espera da troca até o fim do turno. No teste remoto real, Small →
Tiny levou `2,04 s`; o Tiny sobreviveu ao restart e carregou em `0,68 s`; Tiny →
Small levou `2,50 s`. `stt-selection.json` e `tts-selection.json` ficaram em modo
`0600`, o dashboard publicou os três comboboxes e o serviço terminou ativo com zero
reinícios. Na comparação física posterior, o journal mostrou que o turno iniciado
às `18:33:00` usou Whisper Tiny INT8. A troca de volta ocorreu às `18:34:15`, e os
turnos iniciados às `18:34:22`, `18:34:54` e `18:38:43` usaram Small. O usuário
confirmou que o fluxo estava funcionando e o Small permaneceu ativo, concluindo a
aceitação da Fase 11.

Esse teste revelou uma lição de observabilidade: mostrar apenas a seleção atual no
topo não prova qual modelo processou uma fala passada. O `ConversationManager` agora
captura, dentro da trava do turno, `pipeline`, provider/model de STT, LLM e TTS. Os
mesmos IDs sanitizados aparecem no journal e na tabela **Recent turns**. A migração
SQLite conserva o histórico existente; linhas antigas mostram `—` para STT/TTS
porque o sistema não inventa dados que nunca foram coletados.

O schema recebeu `audio_input_tokens`, `audio_cached_input_tokens` e
`audio_output_tokens`, todos zero no pipeline Chained. No Realtime, eles recebem o
uso retornado pela sessão e participam do cálculo com uma tabela de preços datada,
sem armazenar áudio, transcrição, pergunta ou resposta.

Essa evolução passou em 42 testes no Windows e no Raspberry Pi. A implantação
migrou o `usage.db` existente para as oito colunas novas e a API preservou as linhas
antigas com STT/TTS nulos. O serviço voltou saudável no commit `6319ccb`, sem erros
na nova instância, com Small, Qwen local e Jeff selecionados e o assistente no estado
Off persistido pelo usuário. Como o sudo interativo não estava disponível, o
processo antigo foi encerrado uma vez para o `Restart=on-failure` do systemd iniciar
o código novo; por isso essa execução registra `NRestarts=1`.

## Fase 12 — OpenAI Realtime

OpenAI Realtime executa speech-to-speech, mantém estado de conversa e coordena
turnos, interrupções e ferramentas dentro de uma sessão. Por isso, tratá-lo como
apenas mais um modelo no combobox STT ou TTS produziria uma arquitetura incorreta.
A interface ganhará um nível acima:

```text
Voice pipeline
  - Chained (VAD -> STT -> LLM -> TTS)
  - OpenAI Realtime (audio -> realtime session -> audio)
```

Quando **Chained** está ativo, os três seletores continuam disponíveis. Quando
**OpenAI Realtime** está ativo, eles permanecem salvos, mas desabilitados, e o
dashboard mostra `Realtime model` e `Voice`. Voltar para Chained restaura exatamente
as escolhas anteriores. A seleção allowlisted é persistida atomicamente em
`data/pipeline-selection.json` com permissão `0600`.

### Navegador: WebRTC com interface unificada

O navegador cria o `RTCPeerConnection`, a faixa do microfone e o canal de dados.
Ele envia sua oferta SDP para `POST /api/realtime/calls`. O Pi adiciona a configuração
da sessão e chama `/v1/realtime/calls` com `OPENAI_API_KEY`, devolvendo apenas o SDP
de resposta. A chave nunca chega ao JavaScript. Esta é a interface unificada indicada
na documentação atual e evita criar e distribuir um segredo efêmero separadamente.

O canal `oai-events` acompanha detecção de fala, interrupções, texto auxiliar, áudio
e `response.done`. A reprodução usa a faixa remota do próprio WebRTC. A página
consulta o estado sanitizado do Pi e fecha a sessão se o usuário desligar o assistente
ou alterar pipeline, modelo ou voz.

### Raspberry Pi USB: WebSocket half-duplex

Para a P10S, o adaptador mantém uma conexão WebSocket do SDK OpenAI no servidor. O
turno capturado em 16 kHz é reamostrado para PCM16 em 24 kHz, enviado e confirmado
manualmente; cada `response.output_audio.delta` é reproduzido assim que chega. O
microfone continua fechado durante processamento e reprodução. Essa sequência evita
o acesso simultâneo que já travou a interface USB em testes anteriores.

O modelo e a voz são lidos no início de cada turno. Se mudarem, a conexão anterior é
fechada e a próxima fala abre uma nova sessão com a configuração atual. Desligar o
assistente ou voltar a Chained fecha a conexão persistente imediatamente.

### Histórico numérico e custo

Cada `response.done` informa tokens de texto e áudio de entrada, cache e saída. O
backend grava essas contagens, primeiro áudio, duração, modelo, voz, transporte e
custo estimado. Um `response_id` é aceito uma única vez para impedir duplicação.
Áudio, transcrição, prompt e resposta não são gravados. As tarifas ficam no `.env`
com data de referência; isso preserva o valor usado mesmo quando a tabela muda.

O combobox oferece `gpt-realtime-2.1` e `gpt-realtime-2.1-mini`. A tabela de preços
é indexada por modelo, com seis tarifas para cada um: texto e áudio, separados em
entrada, cache e saída. A resolução por maior nome compatível também aceita snapshots
datados sem confundir o Mini com o prefixo do modelo completo. O teste unitário lê o
snapshot salvo no SQLite, além de comparar o custo calculado token a token.

Na implantação ARM64, 49 testes passaram. O diagnóstico do Mini recebeu áudio real
na voz `marin` e informou 35 tokens de entrada, 41 de saída e 76 no total. A API
sanitizada apresentou os dois modelos, aceitou Mini pelo mesmo endpoint do combobox
e voltou ao modelo completo. O estado final permaneceu Chained e Off, com serviço
ativo, `NRestarts=0` e nenhum warning no journal.

### Correção de respostas cortadas

Na prova física, a voz parava no meio de frases longas. O histórico mostrou vários
turnos com `output_tokens=300` e áudio entre 9,7 e 10,5 segundos, tanto no Mini quanto
no modelo completo. Isso comprovou que não era falha da P10S nem da rede: o Realtime
estava reutilizando `OPENAI_MAX_OUTPUT_TOKENS=300` da Responses API.

`REALTIME_MAX_OUTPUT_TOKENS` agora é uma configuração separada, com padrão 2.048,
usada nas sessões WebRTC e WebSocket. O backend USB registra `response.status` e
`status_details.reason`; uma resposta incompleta gera
`REALTIME_USB_RESPONSE_INCOMPLETE`. O navegador também mostra uma mensagem específica
quando o motivo é `max_output_tokens`. O teto maior permite respostas longas, mas a
cobrança continua baseada apenas nos tokens efetivamente gerados.

Após a implantação, 49 testes passaram também no Pi. `/api/system/info` confirmou
`max_output_tokens: 2048`; o restart preservou Realtime, modelo completo, voz `cedar`
e o estado Off escolhidos pelo usuário. O serviço ficou ativo, com `NRestarts=0` e
sem warnings. A suíte também passou a isolar suas expectativas do estado persistido
do dashboard, evitando falsos erros quando o curso testa outra voz ou pipeline.

### Correção de timeout durante reprodução longa no USB

Um teste posterior pediu uma explicação longa sobre a história da IA. A voz tocou
por bastante tempo, parou antes do fim, o turno não apareceu no dashboard e as
perguntas seguintes deixaram de responder. O journal mostrou a sequência decisiva:
`USB_PLAYBACK_STARTED`, seguida cerca de 45 segundos depois por
`USB_CONVERSATION_FAILED` com `TimeoutError`. `arecord` e um `aplay` antigo ficaram
ativos ao mesmo tempo na P10S.

A causa estava no controle de fluxo. Cada delta de áudio do WebSocket era escrito no
`stdin` do `aplay` e aguardava `drain()`. Quando o pipe enchia, o servidor passava a
esperar o alto-falante reproduzir o áudio em tempo real e deixava de ler novos eventos
da OpenAI. Assim, `response.done` não chegava antes do timeout de 45 segundos. Sem
esse evento final, as métricas de tokens e custo não podiam ser gravadas.

O adaptador passou a enfileirar os deltas sem bloquear o leitor do WebSocket. Depois
de `response.done`, `finish()` fecha a entrada e espera o `aplay` consumir o restante.
Em qualquer exceção ou cancelamento, `abort()` mata e limpa o processo parcial. A
mensagem local de falha cria outro player, pois o áudio Realtime usa 24 kHz e a voz
Piper local usa 22,05 kHz. Um teste de regressão comprova que não há `drain()` por
trecho e que uma resposta parcial mata o primeiro player antes do aviso local.

Os 50 testes passaram no Windows e no Raspberry Pi ARM64. Após implantar o commit
`9e6b13d`, o serviço ficou `active/running`, com `NRestarts=0`, sem warnings e sem
processos ALSA enquanto o assistente permanecia Off. A API preservou Realtime,
`gpt-realtime-2.1`, voz `cedar` e o teto de 2.048 tokens. A prova final de uma fala
longa depende do microfone e alto-falante físicos e deve ser feita ao voltar para On.

A documentação oficial consultada em 5 de outubro de 2026 usa
`gpt-realtime-2.1` no exemplo atual, recomenda WebRTC para navegador e WebSocket para
servidor, e orienta novas integrações a usar a interface GA. O modelo usa uma
allowlist configurável, sem dependência permanente desse alias:

- [WebRTC](https://developers.openai.com/api/docs/guides/voice-webrtc)
- [WebSocket](https://developers.openai.com/api/docs/guides/voice-websockets)
- [Conversas Realtime](https://developers.openai.com/api/docs/guides/realtime-conversations)
- [VAD](https://developers.openai.com/api/docs/guides/realtime-vad)
- [Preços](https://developers.openai.com/api/docs/pricing)

### Validação automatizada

Os testes cobrem persistência e allowlist, bloqueio quando Off, troca SDP pela
interface unificada, reamostragem e streaming USB, deduplicação das métricas, migração
do SQLite e cálculo separado de texto/áudio. A aceitação física deve exercitar no
dashboard os dois caminhos: navegador WebRTC e microfone/alto-falante USB.

Na implantação inicial, os 48 testes passaram no Windows e no Raspberry Pi ARM64.
O diagnóstico real do WebSocket recebeu áudio de `gpt-realtime-2.1` com a voz
`marin`; no Pi, a resposta curta informou 35 tokens de entrada e 23 de saída. A API
alternou Realtime → Chained, persistiu o arquivo em modo `0600` e bloqueou uma nova
sessão com `409` enquanto Off. O dashboard respondeu `200`, o serviço permaneceu
ativo, com `NRestarts=0` e sem entradas de warning no journal. Chained e Off foram
restaurados antes da etapa física para evitar consumo involuntário.

# Perguntas frequentes e troubleshooting do curso

## Se OpenAI Realtime aparecer indisponível no dashboard

Confirme que `OPENAI_API_KEY` existe no `.env` e reinicie o serviço, pois a
disponibilidade é calculada na inicialização. Depois confira somente os campos
sanitizados:

```bash
curl --fail http://127.0.0.1:8000/api/system/info
journalctl -u pi-voice-ai.service --since "10 minutes ago" --no-pager
```

Não imprima o `.env` nem a chave nos logs. Uma seleção direta pela API retorna `503`
se a credencial não estiver configurada.

## Se o navegador conectar ao Realtime, mas não tocar áudio

Abra a página por HTTPS, permita o microfone e confirme que **Voice assistant** está
On e **Voice pipeline** está em OpenAI Realtime. Alterar modelo ou voz fecha a sessão
aberta; clique novamente em conectar para usar a nova configuração. O journal deve
mostrar `REALTIME_BROWSER_CALL_CREATED` sem `REALTIME_CALL_REJECTED`.

## Se o Realtime USB parar depois de uma resposta

O modo USB continua half-duplex. Durante a resposta, `arecord` deve ficar fechado e
`aplay` usa a P10S; a captura volta depois. Confira os eventos e o dispositivo sem
reiniciar todo o Raspberry Pi:

```bash
journalctl -u pi-voice-ai.service --since "10 minutes ago" --no-pager
pgrep -af 'arecord|aplay'
arecord -l
aplay -l
```

Se a P10S retornar `Input/output error`, use o procedimento de `usbreset` documentado
nesta seção e reinicie apenas `pi-voice-ai.service`.

Se uma fala longa não aparecer em **Recent turns**, procure `TimeoutError` entre
`USB_PLAYBACK_STARTED` e `USB_CONVERSATION_FAILED`. Também confirme que não existe
um `aplay` órfão junto com `arecord`:

```bash
journalctl -u pi-voice-ai.service --since "10 minutes ago" --no-pager \
  | grep -E 'USB_PLAYBACK|USB_CONVERSATION_FAILED|REALTIME_USB'
pgrep -af 'arecord|aplay'
```

O estado normal em espera tem somente `arecord`; durante a resposta, somente
`aplay`. Se uma versão antiga deixou o player preso, desligue o assistente no
dashboard, encerre esse `aplay`, atualize a aplicação e só então volte para On.

## Se a voz Realtime parar no meio de uma frase

Confira se a linha do turno terminou exatamente no teto configurado e procure o
motivo incompleto:

```bash
journalctl -u pi-voice-ai.service --since "10 minutes ago" --no-pager \
  | grep REALTIME_USB_RESPONSE_INCOMPLETE
```

O padrão atual é `REALTIME_MAX_OUTPUT_TOKENS=2048`. Mantenha respostas normalmente
concisas e aumente esse valor somente quando o caso de uso exigir falas ainda maiores.

## Como confirmar os tokens e o custo do Realtime

Abra `/dashboard.html`. Uma linha Realtime mostra o pipeline, `gpt-realtime-2.1`, a
voz OpenAI, tokens totais e as colunas de áudio de entrada e saída. O custo combina
as seis tarifas configuradas para texto e áudio. O banco guarda apenas números e IDs
técnicos; ele não contém a gravação nem o conteúdo falado.

## Se eu selecionar llama.cpp e o modelo local estiver desligado?

O dashboard mostra o provedor como indisponível e desativa a aplicação da escolha.
Mesmo que uma chamada seja feita diretamente, a API responde `503` e conserva a
seleção anterior. Verifique:

```bash
systemctl status pi-voice-ai-llm.service --no-pager
curl --fail http://127.0.0.1:8081/health
journalctl -u pi-voice-ai-llm.service --since "10 minutes ago" --no-pager
```

## Desliguei no dashboard, mas quero confirmar que o microfone USB parou

Com a chave em **Off**, `arecord` não deve aparecer e a API deve informar
`"enabled": false`. Ao religar, o processo é recriado sem reboot:

```bash
pgrep -a arecord
curl -k https://127.0.0.1:8443/api/system/info
journalctl -u pi-voice-ai.service --since "5 minutes ago" --no-pager
```

Procure `USB_AUDIO_STOPPED` ao desligar e `USB_AUDIO_STARTED` ao ligar. Se o
dashboard não refletir a escolha após reiniciar, confira a permissão de
`data/assistant-state.json` sem publicar seu conteúdo junto com outros dados locais.

Na primeira validação, cada mudança produziu dois eventos USB. O processo era
iniciado com `python -m app.main`, mas `uvicorn.run("app.main:app")` importava o
módulo novamente e registrava uma segunda cópia dos callbacks globais. Passar o
objeto `app` já carregado para `uvicorn.run(app)` removeu a segunda importação.
Esse diagnóstico mostra por que logs duplicados devem ser investigados mesmo quando
o resultado visível parece correto.

A implantação seguinte parou no gate de testes porque o Pi conservou corretamente
o estado **Off**, enquanto um teste antigo do endpoint presumiu implicitamente que
o assistente estava ligado. O teste passou a fornecer um controle **On** isolado.
Estados persistentes são parte da entrada de um teste e precisam ser declarados;
caso contrário, a suíte pode passar em uma máquina limpa e falhar no dispositivo.

Depois das correções, 33 testes passaram no Pi. Off encerrou `arecord`, salvou o
arquivo em modo `0600`, bloqueou o endpoint com HTTP 409 e não alterou os 24 turnos
nem os 6.268 tokens existentes. Um restart preservou Off sem processo de captura.
On abriu um novo `arecord` e emitiu uma única sequência de eventos; o Off final
encerrou a captura novamente. Os serviços principal e llama.cpp permaneceram
ativos, com `NRestarts=0`, `ExecMainStatus=0` e nenhum erro recente.

## A escolha do LLM voltou depois de um reboot?

Confira `data/llm-selection.json` sem publicar outros arquivos de `data/`. Se ele
não existir, `LLM_PROVIDER` define a seleção inicial. O serviço deve ter permissão
de escrita no diretório do projeto. Um provedor ou modelo removido da lista é
ignorado com segurança e o padrão configurado volta a ser usado.

## Por que a resposta local pode ser mais lenta que a OpenAI?

O Raspberry Pi compartilha quatro núcleos entre STT, LLM e TTS. O modelo local
elimina rede e custo de API, mas gera tokens apenas com a CPU. Respostas curtas,
contexto de 2.048 tokens, Q4_K_M e raciocínio desativado reduzem a espera. Compare
qualidade e tokens/s antes de escolher um modelo menor.

Esta seção deve ser apresentada como diagnóstico baseado em evidências. Em cada
caso, comece pelo sintoma, confira o estado atual, altere somente o componente com
problema e repita uma verificação objetiva.

## Como obter um diagnóstico geral do serviço?

Use primeiro comandos somente de leitura:

```bash
systemctl status pi-voice-ai.service --no-pager
systemctl show pi-voice-ai.service \
  -p ActiveState -p SubState -p NRestarts -p ExecMainStatus
journalctl -u pi-voice-ai.service --since "10 minutes ago" --no-pager
```

`ActiveState=active`, `SubState=running`, `ExecMainStatus=0` e `NRestarts=0` indicam
um processo estável. Procure `ERROR`, `Traceback`, `APP_STARTED` e o evento da etapa
que deveria ter ocorrido. Um health check HTTP confirma o servidor, mas não prova
sozinho que microfone, modelo e alto-falante estão funcionando.

## O dashboard pode mostrar os modelos realmente ativos?

Sim. A seção **Tecnologia ativa** consulta `/api/system/info` e apresenta versão,
LLM, STT, TTS, modo de áudio e VAD. Use essa informação antes de diagnosticar uma
mudança de qualidade: ela confirma, por exemplo, se o Whisper Small INT8 em português
está realmente carregado. A API omite chaves, caminhos e conteúdo das conversas.

## O modelo correto está ativo, mas passou a entender pior

Em um diagnóstico posterior ao marco 1.0, o Pi continuava saudável, com Whisper
Small, português, três threads, captura no máximo e sem warnings. Os três turnos
recentes tinham apenas 2,020 s, 0,548 s e 2,436 s. RMS e pico estavam baixos, sem
clipping. Isso indicou sinal fraco e corte da frase, não troca de modelo.

A correção aumentou o silêncio final de 1,0 para 1,2 s, reduziu o limiar do Silero
de 0,5 para 0,4 e habilitou normalização local limitada antes do Whisper:

```dotenv
VAD_THRESHOLD=0.4
VAD_MIN_SILENCE_SECONDS=1.2
STT_NORMALIZE_AUDIO=true
STT_TARGET_PEAK=0.8
STT_MAX_GAIN=12
```

O ganho máximo evita amplificação sem limite. Confira `STT_AUDIO_NORMALIZED` e
`CONVERSATION_STT_STARTED` no journal, fale a cerca de 15–30 cm do microfone e
compare uma frase de pelo menos três segundos antes de mudar novamente o modelo.

## Por que `id\_ed25519.pub` não foi encontrado no Windows?

**Sintoma:** `ssh-keygen -lf` informou `No such file or directory`.

**Causa observada:** a barra invertida antes do sublinhado veio da formatação do
texto e virou parte do nome. O arquivo padrão chama-se `id_ed25519.pub`.

**Diagnóstico e solução:**

```powershell
Get-ChildItem (Join-Path $env:USERPROFILE '.ssh')
ssh-keygen -lf (Join-Path $env:USERPROFILE '.ssh\id_ed25519.pub')
```

Copie somente o arquivo `.pub` ao Pi. A chave privada sem `.pub` permanece no
Windows. Verifique a autenticação com `ssh voicepi "hostname"`.

## O endereço IP do Raspberry Pi mudou. Preciso alterar o projeto?

O endereço não é gravado no código ou no `.env` da aplicação. O alias SSH deve usar
o hostname quando a rede o resolve:

```sshconfig
Host voicepi
    HostName home-ai.local
    User cristiano
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

Teste `ssh voicepi "hostname"`. Se mDNS não funcionar, altere apenas `HostName` no
arquivo SSH do Windows ou configure uma reserva DHCP no roteador.

## Por que o primeiro health check falhou logo após instalar o serviço?

**Sintoma:** `curl` não conectou à porta enquanto o systemd já havia criado e
habilitado a unidade.

**Causa observada:** o teste ocorreu antes de o Uvicorn abrir a porta.

**Solução:** `scripts/healthcheck.sh` passou a repetir a tentativa por até 20
segundos. Confirme separadamente:

```bash
systemctl is-active pi-voice-ai.service
./scripts/healthcheck.sh
```

## Por que HTTPS funciona pelo hostname, mas falha por `127.0.0.1` ou por outro IP?

O certificado de desenvolvimento precisa conter exatamente o nome usado na URL.
Durante o health check local, o projeto usa o hostname coberto pelo certificado e
resolve esse nome para loopback. No navegador, abra o hostname ou IP incluído quando
o certificado foi criado. Se o IP mudar e não estiver no certificado, prefira o
hostname estável ou gere um novo certificado de desenvolvimento.

## O navegador não libera o microfone

Confirme que a página usa HTTPS, que o certificado está confiável no Windows e que
a permissão do microfone foi concedida para esse site. Feche peers antigos antes de
repetir o teste. O endpoint de remoção é idempotente, então uma segunda solicitação
de fechamento pode retornar sucesso mesmo quando a conexão já foi limpa.

## A transcrição troca algumas palavras

O Whisper Tiny foi escolhido no benchmark curto da Fase 8 pela menor latência. No
uso físico contínuo em português, porém, o usuário aprovou o Whisper Small INT8 por
entender as falas com muito mais consistência. O custo observado foi uma espera de
aproximadamente cinco a seis segundos em algumas perguntas. A configuração atual
prioriza essa precisão; Tiny continua disponível para comparar latência.

Quando a dificuldade se tornou frequente no microfone USB, os logs mostraram vários
segmentos curtos, entre 0,49 s e 0,94 s. O diagnóstico passou a registrar somente
pico, RMS e percentual de saturação antes do STT. Essas medidas ajudam a separar
volume baixo, distorção e corte precoce do VAD sem guardar áudio nem transcrição. Um
teste com `VAD_MIN_SILENCE_SECONDS=1.2` permite pausas naturais maiores antes de
encerrar a frase; a troca de modelo deve ocorrer somente após essa comparação.

## A OpenAI terminou uma chamada sem texto

Esse comportamento apareceu em testes reais. O pipeline faz uma única repetição
somente quando a conclusão vem vazia e mantém qualquer falha posterior explícita nos
logs. Procure `CONVERSATION_LLM_EMPTY_RETRY`. Uma repetição bem-sucedida terá depois
`ASSISTANT_DONE`; repetidas falhas exigem verificar chave, modelo, rede e resposta da
API sem registrar a chave ou o conteúdo privado.

## O microfone funcionou, mas uma falha de rede deixou o assistente em silêncio

Um caso real chegou ao LLM e falhou com `Temporary failure in name resolution`.
Isso indica indisponibilidade de DNS ou rede, não defeito do microfone. Verifique:

```bash
getent hosts api.openai.com
ping -c 1 1.1.1.1
journalctl -u pi-voice-ai.service --since "5 minutes ago" --no-pager
```

O adaptador USB agora tenta falar `USB_ERROR_MESSAGE` usando o TTS local quando um
turno falha. Depois retorna ao estado pronto, permitindo repetir a pergunta quando a
rede voltar. Se até esse aviso falhar, procure `USB_ERROR_MESSAGE_FAILED` nos logs.

## O modo USB está ativo, mas falar não produz resposta

**Sintoma observado:** o serviço estava ativo e `arecord` aparecia como processo,
mas não havia eventos `USB_VAD_SPEECH_STARTED` e nenhum áudio retornava.

**Diagnóstico inicial:**

```bash
arecord -l
aplay -l
pgrep -a arecord
pgrep -a aplay
amixer -c P10S contents
journalctl -u pi-voice-ai.service --since "10 minutes ago" --no-pager
```

No caso real, a saída `PCM Playback Volume` estava em zero, um `aplay` usado no
diagnóstico anterior continuou aberto e o endpoint de captura parou de entregar
frames. Um teste nativo retornou zero bytes e `Input/output error`.

Pare o serviço antes de testar o dispositivo isoladamente:

```bash
sudo systemctl stop pi-voice-ai.service
pgrep -a arecord
pgrep -a aplay
```

Encerre somente processos identificados como pertencentes ao teste. Se a captura
continuar sem frames, resete apenas a interface conhecida e restaure os níveis:

```bash
sudo usbreset 1234:5684
amixer -c P10S sset PCM 75% unmute
amixer -c P10S sset Mic 100% cap
```

O formato nativo informado pela P10S é `S16_LE`, 48 kHz e dois canais. A verificação
real produziu 192.000 bytes em um segundo:

```bash
timeout 4 arecord -q -D hw:CARD=P10S,DEV=0 \
  -d 1 -t raw -f S16_LE -c 2 -r 48000 | wc -c
```

Depois, reinicie e procure a sequência `USB_AUDIO_STARTED`, `USB_VAD_SPEECH_STARTED`,
`CONVERSATION_TURN_COMPLETED`, `USB_PLAYBACK_COMPLETED` e `USB_CONVERSATION_READY`:

```bash
sudo systemctl restart pi-voice-ai.service
systemctl is-active pi-voice-ai.service
journalctl -u pi-voice-ai.service -f
```

Nas versões seguintes ao primeiro diagnóstico, o próprio serviço restaura os níveis
definidos por `USB_PLAYBACK_VOLUME_PERCENT` e `USB_CAPTURE_VOLUME_PERCENT` durante a
inicialização. Os comandos manuais continuam úteis para testar o hardware isolado.

Na Fase 10, `USB_CAPTURE_RETRY_SECONDS=3` reinicia automaticamente uma captura que
encerrou e `USB_ZERO_STREAM_SECONDS=10` detecta um fluxo digital totalmente zerado.
Procure `USB_CAPTURE_RETRY_SCHEDULED`, `USB_CAPTURE_RESTARTED` e
`USB_CAPTURE_ZERO_STREAM` no journal. Essa recuperação não reinicia o Raspberry Pi.

O sintoma reapareceu durante a avaliação do Whisper Small: serviço, modelo e
`arecord` estavam ativos, mixer em 75%/100%, mas não surgiam eventos de fala. O Pi
não havia reiniciado. Resetar somente a interface P10S com `usbreset 1234:5684` e
reiniciar o serviço recriou a captura, sem reboot do sistema operacional.

O mesmo diagnóstico foi necessário depois de mudar a chave do dashboard para
**On**. A API confirmou `enabled=true`, `arecord` foi recriado e o mixer estava em
100%, mas nenhum evento `USB_VAD_SPEECH_STARTED` apareceu. Com o assistente em
**Off**, o teste nativo falhou imediatamente com `pcm_read: Input/output error`.
Após `sudo usbreset 1234:5684` e o restart do serviço, a captura produziu 384.044
bytes em dois segundos. A chave foi então colocada em **On** novamente. Isso mostra
que o estado do dashboard e o processo `arecord` confirmam o controle lógico, mas
um teste nativo ainda é necessário quando o endpoint USB fica travado.

Minutos depois, a primeira conversa funcionou e a captura voltou a travar exatamente
após `USB_PLAYBACK_COMPLETED`. O processo `arecord` ainda aparecia, mas duas novas
perguntas não geraram eventos VAD; isolada novamente, a P10S produziu apenas o
cabeçalho WAV de 44 bytes e `Input/output error`. A causa era o uso simultâneo da
mesma interface por `arecord` e `aplay`: desativar barge-in apenas descartava frames,
sem fechar a captura. O adaptador passou a encerrar `arecord` depois de detectar a
pergunta, aguardar a liberação do processo antes de iniciar STT/LLM/TTS e reabrir a
captura após a reprodução. Confira no journal:

```text
USB_CAPTURE_PAUSED_FOR_TURN
USB_PLAYBACK_COMPLETED
USB_CONVERSATION_READY
USB_CAPTURE_RESUMED_AFTER_TURN
```

Essa sequência preserva o barge-in quando habilitado e usa acesso exclusivo no modo
padrão, compatível com a limitação observada na P10S.

## Por que o barge-in USB começa desativado?

O navegador dispõe de processamento acústico próprio. Na ligação USB direta, a voz
do alto-falante pode voltar ao microfone e parecer uma nova fala. Primeiro ajuste o
volume, a distância e a direção física. Depois habilite `USB_ENABLE_BARGE_IN=true`,
reinicie e confirme nos logs que a reprodução não dispara interrupções sozinha.

O endpoint sanitizado `/api/system/info` informa `audio.barge_in`, e o dashboard
mostra **voice interruption on/off** em **Audio and VAD**. Com o recurso ativo,
`arecord` permanece aberto enquanto `aplay` fala. O início de uma nova fala detectado
pelo Silero cancela a geração e a reprodução atuais e conserva o áudio da nova frase
para o turno seguinte. O teste automatizado confirma o cancelamento da tarefa e do
player; o teste físico continua indispensável para avaliar eco no ambiente real.

## Que informações nunca devem aparecer em uma aula ou diagnóstico publicado?

Não mostre a chave privada SSH, senha, `OPENAI_API_KEY`, conteúdo do `.env`, chave
TLS privada ou endereço de rede privada sem necessidade. Prefira eventos, tempos,
contagens, nomes de configuração e saídas sanitizadas.
