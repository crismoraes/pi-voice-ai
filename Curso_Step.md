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

O commit inicial, push e `v0.1.0` aguardam a validação completa da Fase 0. A
implementação de aplicação pertence à Fase 1 e não foi iniciada.

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
