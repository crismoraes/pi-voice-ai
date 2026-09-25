# Changelog

## [Unreleased]

### Added

- Fundação FastAPI com endpoint `GET /health` independente de serviços externos.
- Configuração validada por ambiente e logs estruturados em JSON.
- Teste ASGI do endpoint de saúde.
- Bootstrap ARM64, deployment validado, controle de serviço e health check.
- Unidade systemd renderizada para o usuário e caminho reais do Raspberry Pi.

### Validated

- Bootstrap e dependências Python ARM64 no Raspberry Pi 5.
- Teste, compilação e endpoint `/health` pela rede local.

### Pending

- Instalação e validação do serviço systemd com sudo interativo.

## [0.1.0] - 2026-09-25

### Added

- Fundação documental do PiVoice AI: README, registro didático da Fase 0 e changelog.
- Inventário verificado do Windows e das ferramentas de desenvolvimento.
- Chave ED25519 dedicada ao projeto instalada e validada no Raspberry Pi.
- Alias SSH `voicepi` configurado e validado para execução remota por chave.
- Inventário do Raspberry Pi 5, sistema ARM64 e recursos coletado remotamente.
- Procedimento de reprodução do SSH com ED25519, transferência da chave pública
  por USB, instalação sem duplicatas e alias `voicepi`.
- `.gitignore` para credenciais, chaves privadas, ambientes e arquivos gerados.
- `.env.example` sem credenciais, reservado às futuras fases.

### Validated

- Autenticação SSH por chave, alias `voicepi` e execução remota.
- Raspberry Pi 5 Model B, arquitetura ARM64, sistema, Python, Git, RAM, disco,
  temperatura e estado de throttling.
- Repositório local limpo e sincronizado com `origin/main`, sem segredos rastreados.
