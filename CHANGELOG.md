# Changelog

## [Unreleased]

### Added

- Abstração substituível de LLM e adaptador para a OpenAI Responses API.
- Endpoint SSE que transmite deltas, primeiro token e tempo total ao navegador.
- Interface web que envia a transcrição e exibe incrementalmente a resposta.
- Verificador do streaming LLM contra uma implantação HTTPS real.

### Changed

- Versão de desenvolvimento avançada para `0.4.0.dev0`.
- Modelo padrão configurado como `gpt-6-luna`, com saída limitada a 300 tokens.

### Validated

- Nove testes locais e uma chamada real mínima à Responses API.

## [0.3.0] - 2026-09-26

### Added

- Pipeline local de STT com interface substituível e Whisper Tiny via sherpa-onnx.
- Captura manual de frases WebRTC, reamostragem mono em 16 kHz e limite de 30 s.
- APIs para iniciar e finalizar transcrições e interface web para exibir resultados.
- Download idempotente do modelo com checksum e scripts de benchmark e teste ao vivo.

### Validated

- Seis testes no Windows e Raspberry Pi ARM64, incluindo captura WebRTC com STT falso.
- Wheels ARM64 de sherpa-onnx e NumPy instalados sem compilação.
- Whisper Tiny real no Pi com RTF de `0,171` em uma referência inglesa de 6,625 s.
- Fluxo implantado validado do Windows ao Pi por WebRTC, com RTF de `0,175`.
- Transcrição física validada com várias frases reais em português no navegador;
  a última teve 18,06 s, processamento de 3,346 s e RTF de `0,185`.

### Changed

- Versão publicada como `0.3.0`.
- Bootstrap instala o modelo STT em `models/`, fora do Git.

### Fixed

- Teste STT ao vivo ignora proxies do ambiente para alcançar a rede local.
- Duração de áudio do teste ao vivo usa corretamente a base de tempo do PyAV.

## [0.2.0] - 2026-09-25

### Added

- Transporte WebRTC com signaling HTTP e loopback da faixa de áudio.
- Cliente de navegador para captura, estado da conexão e reprodução do áudio.
- Suporte opcional a TLS direto no Uvicorn e health check HTTPS com CA confiável.
- Teste de integração com dois peers reais e retorno de frame de áudio.
- Verificador do loopback WebRTC contra uma implantação HTTPS em execução.
- Fundação FastAPI com endpoint `GET /health` independente de serviços externos.
- Configuração validada por ambiente e logs estruturados em JSON.
- Teste ASGI do endpoint de saúde.
- Bootstrap ARM64, deployment validado, controle de serviço e health check.
- Unidade systemd renderizada para o usuário e caminho reais do Raspberry Pi.

### Validated

- Bootstrap e dependências Python ARM64 no Raspberry Pi 5.
- Teste, compilação e endpoint `/health` pela rede local.
- Serviço systemd ativo, habilitado, sem reinícios e sem erros recentes no journald.
- Health check corrigido no Pi e acesso HTTP pela rede local.
- Testes WebRTC aprovados no Windows e no Raspberry Pi ARM64.
- HTTPS implantado no Pi com permissões restritas e validação de CA e hostname.
- Loopback WebRTC real validado do Windows até o Pi, incluindo conexão e cleanup.
- Loopback audível validado no navegador com microfone e alto-falante reais.

### Fixed

- Health check agora aguarda o Uvicorn ficar pronto após restart do systemd.
- Health check HTTPS usa o hostname certificado e o resolve localmente para loopback.
- Encerramento WebRTC repetido retorna sucesso quando o peer já foi removido.

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
