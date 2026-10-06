# Changelog

## [Unreleased]

### Added

- Avatar 2D em SVG na conversa web, com estados de escuta, processamento e fala,
  piscadas e boca sincronizada ao RMS do áudio WebRTC via Web Audio API.
- Botão **Stop speaking** e endpoint `POST /api/system/assistant/interrupt` para
  cancelar de forma determinística a resposta USB atual e retomar a captura.
- Estado sanitizado de interrupção por voz em `/api/system/info` e no painel
  **Audio and VAD**.
- `gpt-realtime-2.1-mini` no seletor Realtime, com tarifas próprias de texto,
  áudio e cache e resolução correta de aliases e snapshots datados.
- Seletor persistente **Voice pipeline** entre Chained e OpenAI Realtime, com
  modelo e voz Realtime em allowlists configuráveis.
- WebRTC nativo do OpenAI Realtime no navegador pela interface unificada
  `/v1/realtime/calls`; a chave OpenAI permanece no backend.
- WebSocket Realtime persistente para áudio USB no Raspberry Pi, com captura e
  reprodução half-duplex compatíveis com a interface P10S.
- Contabilização separada de tokens de texto, áudio e cache do Realtime, com
  estimativa de custo e identificação do pipeline em **Recent turns**.
- APIs `PUT /api/system/pipeline`, `POST /api/realtime/calls` e
  `POST /api/realtime/usage`.
- Chave persistente **Voice assistant On/Off** no dashboard para interromper a
  captura USB, pausar WebRTC e impedir novos consumos de LLM durante desenvolvimento.
- API `PUT /api/system/assistant` e estado local atômico com permissão `0600`.
- Seleção persistente e allowlisted de LLM entre OpenAI e llama.cpp no dashboard.
- Adaptador streaming para o endpoint de chat do llama.cpp, com tokens e tokens/s.
- Qwen3.5 2B Q4_K_M local, download com SHA-256, build ARM64 fixado e serviço
  systemd restrito ao loopback.
- Dashboard integralmente em inglês, com seletores de provedor e modelo.
- Painel de tecnologia ativa no topo do dashboard com versão, modelos LLM, STT e
  TTS, execução local/nuvem, modo de áudio, VAD e parâmetros sanitizados.
- API `/api/system/info` sem credenciais ou caminhos privados.
- Normalização local e limitada do áudio antes do Whisper, configurável por pico
  alvo e ganho máximo.
- Seletores STT e TTS no dashboard, com Whisper Small/Tiny INT8 e Piper Jeff,
  allowlist, disponibilidade, persistência atômica e rollback de carregamento.
- APIs `PUT /api/system/stt` e `PUT /api/system/tts` e opções sanitizadas em
  `/api/system/info`.
- Colunas de pipeline, STT, LLM e TTS realmente usados por conversa na tabela
  **Recent turns**, com migração preservando o histórico existente.
- Campos numéricos de tokens de áudio de entrada/saída preparados para as métricas
  e custos do OpenAI Realtime, sem armazenar conteúdo da conversa.

### Changed

- Barge-in USB voltou a ficar desativado na instalação P10S após o teste físico
  comprovar falsas interrupções causadas pelo retorno do alto-falante no microfone.
- **Recent turns** agora usa cartões responsivos com custo, modelos, tokens e tempo
  visíveis sem rolagem horizontal.
- Realtime passa a usar `REALTIME_MAX_OUTPUT_TOKENS=2048`, separado do limite de
  300 tokens da Responses API, para não cortar áudio por volta de dez segundos.
- Versão de desenvolvimento elevada para `1.2.0.dev0`.
- O SDK OpenAI é instalado com o extra `realtime` para suportar o transporte
  WebSocket no servidor.
- A página principal escolhe automaticamente o transporte Chained ou Realtime e
  encerra a sessão direta quando Off, pipeline, modelo ou voz mudam no dashboard.
- `httpx` passa a ser dependência de runtime para o servidor local.
- Limiar padrão do Silero VAD ajustado para `0.4` e silêncio final para `1.2 s`
  após falas reais curtas e sinal baixo no microfone USB.
- Turnos completos agora seguram uma trava de seleção para impedir mudanças de STT,
  LLM ou TTS no meio de uma resposta.
- Logs de início do STT e conclusão do turno incluem IDs sanitizados dos modelos
  para relacionar diagnósticos com o histórico numérico.

### Fixed

- Restart com uma conexão longa do navegador aberta agora limita o encerramento
  gracioso do Uvicorn a cinco segundos, deixando tempo para o cleanup antes do
  `TimeoutStopSec` do systemd.
- Reprodução USB longa não bloqueia mais a leitura do WebSocket Realtime esperando
  `aplay` consumir cada trecho. O evento `response.done` volta a registrar tokens e
  custo antes da espera final pelo alto-falante.
- Falhas e cancelamentos de turnos USB agora encerram qualquer `aplay` parcial; o
  aviso local usa um player novo para aceitar a frequência de 22,05 kHz do Piper
  depois dos 24 kHz do Realtime.
- Respostas Realtime interrompidas no meio da fala ao atingir exatamente 300 tokens.
  USB agora registra status/motivo incompleto no journal e o navegador informa o
  encerramento incompleto na interface.
- Inicialização do Uvicorn deixa de reimportar `app.main`, evitando callbacks e
  eventos duplicados ao alternar o estado do assistente.
- Teste do endpoint de streaming agora isola explicitamente o estado On e não
  depende do estado persistido usado pelo Raspberry Pi.
- Interface P10S travada após uma retomada em On foi recuperada com reset somente
  do dispositivo USB e restart do serviço, sem reboot do Raspberry Pi.
- Captura USB agora fecha antes do processamento e da reprodução quando o barge-in
  está desligado, evitando que `arecord` e `aplay` travem a P10S em acesso simultâneo.

### Validated

- Avatar SVG validado no HTTPS implantado em captura de navegador de 1.100 × 1.400;
  os mesmos 53 testes passaram no Windows e no Raspberry Pi ARM64.
- Cinquenta e três testes passaram no Windows e no Pi ARM64. O botão implantado
  interrompeu uma resposta com 1,949 segundo pendente e a captura USB voltou
  imediatamente, sem warnings ou reinícios do serviço.
- Cinquenta e um testes passaram no Windows e no Pi ARM64. Uma captura real em
  1.440 px confirmou os cartões sem overflow horizontal; a API confirmou barge-in
  USB ativo e o restart seguinte terminou sem timeout do systemd.
- Cinquenta testes passaram no Windows e no Raspberry Pi ARM64 após desacoplar a
  recepção Realtime da reprodução USB. O serviço implantado ficou ativo, sem
  reinícios, warnings ou processos ALSA com o assistente Off.
- A correção passou nos 49 testes Windows/ARM64; o Pi expôs o teto 2.048, preservou
  Realtime/`gpt-realtime-2.1`/`cedar` e Off, com `NRestarts=0` e journal sem alertas.
- Testes de API foram isolados das preferências persistidas após a suíte detectar
  corretamente que o usuário havia selecionado Realtime e `cedar` no dashboard.
- O Mini respondeu com áudio real na voz `marin` e informou 35 tokens de entrada,
  32 de saída e 67 no total; 49 testes passaram após a precificação por modelo.
- No ARM64, os mesmos 49 testes passaram; o Mini entregou áudio e 76 tokens no
  diagnóstico. A API expôs os dois modelos, aplicou Mini e restaurou o completo,
  mantendo Chained, Off, `NRestarts=0` e journal sem alertas.
- Quarenta e oito testes passaram no Windows e no Raspberry Pi ARM64. O teste real
  do WebSocket recebeu áudio de `gpt-realtime-2.1` com a voz `marin` e métricas de
  tokens nas duas plataformas.
- No Pi, Realtime → Chained persistiu em arquivo `0600`, Off bloqueou uma nova
  chamada com `409`, o dashboard respondeu `200` e o estado final preservou Chained
  e Off. Serviço ativo, `NRestarts=0` e nenhum alerta após a implantação `084f5b4`.
- Chave Off encerrou `arecord`, persistiu com modo `0600`, bloqueou o LLM com 409
  e manteve inalterados 24 turnos e 6.268 tokens; On recriou a captura e Off voltou
  a encerrá-la, com eventos únicos, zero reinícios e sem erros.
- Após o reset da P10S, a captura nativa produziu 384.044 bytes em dois segundos;
  o serviço voltou ativo, sem reinícios, com um único `arecord` e estado On.
- Trinta e quatro testes aprovados após adicionar a sincronização entre captura e
  reprodução USB.
- Perguntas físicas consecutivas confirmaram captura e reprodução estáveis depois
  de remover o acesso simultâneo do `arecord` e `aplay` à P10S.
- Quarenta testes aprovados no Windows para a implementação inicial da Fase 11.
- Quarenta testes aprovados também no Pi; Small → Tiny → restart → Small confirmou
  troca e persistência, arquivos `0600`, dashboard atualizado e serviço sem reinícios.
- O journal confirmou Tiny no turno das `18:33:00` e Small nos turnos a partir de
  `18:34:22`; o usuário confirmou o fluxo e concluiu a aceitação física da Fase 11.
- Quarenta e dois testes passaram no Windows e no Pi; o banco existente migrou sem
  perda, a API expôs o novo contrato e o serviço implantado ficou saudável e sem
  erros após iniciar o commit `6319ccb`.
- Trinta e três testes aprovados no Windows e no Raspberry Pi ARM64.
- Qwen local com primeiro texto em 1,221 s e 6,01 tokens/s no benchmark; endpoint
  da aplicação com primeiro texto em 1,495 s e resposta curta em 2,626 s.
- Troca OpenAI/llama.cpp nos dois sentidos e persistência local após reinício.
- Tokens locais armazenados sem custo de nuvem; ambos os serviços ativos com zero
  reinícios, sem erros, 5,3 GiB disponíveis, 46,6 °C e sem throttling.

## [1.0.0] - 2026-09-26

### Added

- Supervisão da captura USB com reabertura do `arecord` após encerramento e
  watchdog configurável para fluxo PCM totalmente zerado.
- Diagnóstico sanitizado de systemd, endpoints, ALSA, recursos e journal em
  `scripts/diagnose_pi.sh`.
- Métricas sanitizadas de pico, RMS e saturação do áudio antes do STT para
  diagnosticar qualidade do microfone sem registrar fala ou transcrição.
- Histórico local SQLite com tokens de entrada, cache, saída e raciocínio informados
  pela Responses API, latências por fala e custo estimado com tarifas configuráveis.
- Dashboard responsivo com totais, gráfico diário, filtros por período e últimas
  falas, sem armazenar áudio, transcrição ou texto da resposta.
- APIs somente leitura em `/api/usage/summary` e `/api/usage/turns`.

### Changed

- Bootstrap instala o modelo Whisper selecionado no `.env`, com suporte reproduzível
  a Tiny e Small e verificação SHA-256 de ambos.
- Whisper Small INT8, três threads e 1,0 s de silêncio final passam a ser os padrões
  após a validação física em português.
- O health check de implantação também valida o dashboard e a API de consumo.
- Banco local de consumo recebe permissão `0600` em sistemas POSIX.
- O contrato de LLM pode entregar metadados finais de uso junto ao streaming.
- Versão publicada como `1.0.0`, concluindo as Fases 0 a 10.

### Validated

- Vinte e quatro testes aprovados no Windows e no Raspberry Pi ARM64.
- Encerramento controlado do `arecord` recuperado em três segundos, com restauração
  do mixer, novo processo de captura e serviço continuamente ativo.
- Reboot real preservou a inicialização automática, captura USB, endpoints e banco;
  `NRestarts=0`, `ExecMainStatus=0`, sem throttling nem erros no journal do boot.
- Conversa física após o reboot concluída com reconhecimento e resposta USB;
  o usuário confirmou funcionamento perfeito.

## [0.9.0] - 2026-09-26

### Added

- Adaptador ALSA para conversa local com microfone e alto-falante USB.
- Configuração de dispositivos USB, período de captura e barge-in local.
- Restauração automática dos níveis ALSA de captura e reprodução na inicialização.
- Aviso falado local e configurável quando um turno USB não pode ser concluído.
- Testes do ciclo de vida do `arecord` e do streaming PCM para um único `aplay`.

### Changed

- Versão publicada como `0.9.0`.
- Bootstrap passa a instalar `alsa-utils` quando `arecord` ou `aplay` não existem.
- Encerramento esperado do `arecord` durante reinícios deixa de ser registrado como erro.
- Barge-in USB permanece opt-in para instalações sem cancelamento acústico de eco.

### Hardware

- Interface bidirecional P10S identificada por ALSA como
  `plughw:CARD=P10S,DEV=0`, com captura e reprodução USB.

### Validated

- Conversa física concluída pelo microfone e alto-falante USB: 3,244 s de fala,
  STT em 0,540 s e 18,472 s de resposta reproduzidos em cinco trechos.
- Diagnóstico da P10S recuperou captura após remover um processo antigo, restaurar
  volume e resetar o endpoint USB; a captura nativa entregou 192.000 bytes por segundo.
- Testes confirmam os comandos de mixer antes da abertura do `arecord`.
- Vinte testes aprovados, incluindo a reprodução do aviso após falha da conversa.
- Perguntas frequentes do curso reúnem os problemas reais e seus procedimentos de
  diagnóstico, correção e verificação.

## [0.8.0] - 2026-09-26

### Added

- Streaming de TTS por sentenças com evento `tts_chunk` e tempo até o primeiro áudio.
- Seleção `int8`/`fp32` e descoberta do tamanho do modelo Whisper pelo diretório.
- Benchmark reproduzível de limites de trecho TTS.
- Pré-carregamento paralelo dos modelos STT e TTS durante a inicialização.

### Changed

- Versão publicada como `0.8.0`.
- Relay da captura WebRTC sem fila intermediária para priorizar áudio recente.

### Validated

- Linha de base de uma a quatro threads para STT e TTS no Raspberry Pi 5.
- STT Tiny INT8 com mediana aproximada de 0,324 s em três threads para 1,467 s de áudio.
- TTS curto com mediana aproximada de 0,182 s em três threads, contra 0,218 s em duas.
- Tiny INT8/FP32 com medianas de 0,325/0,426 s; Base INT8/FP32 com
  0,719/0,969 s no mesmo WAV de 1,467 s. Tiny INT8 também teve o melhor texto.
- Limite TTS de 240 caracteres: primeiro trecho em cerca de 0,605 s e total de
  2,449 s no texto longo, sem o custo das divisões menores.
- WebRTC implantado com primeiro áudio em 0,257 s e 0,362 s em turnos aquecidos.
- Pré-carregamento reduziu o primeiro áudio após reinício de 1,652 s para 0,586 s.
- Dezessete testes aprovados no Windows e no Raspberry Pi ARM64.
- Validação física produziu 43,75 s de voz em 12 trechos; o primeiro áudio ficou
  disponível em 0,462 s e a síntese completa levou 7,323 s, sem erros no turno.

## [0.7.0] - 2026-09-26

### Added

- Barge-in por VAD durante processamento e reprodução da resposta automática.
- Evento SSE `interrupted` com fase do turno e áudio pendente descartado.
- Verificador WebRTC que envia uma segunda fala durante a primeira resposta.
- Nova tentativa única quando o modelo conclui uma resposta sem produzir texto.

### Changed

- Versão publicada como `0.7.0`.
- O VAD permanece ativo enquanto a conversa está ocupada quando
  `ENABLE_BARGE_IN=true`.

### Validated

- Dezesseis testes no Windows e no Raspberry Pi, incluindo cancelamento da reprodução,
  limpeza do áudio e início do turno seguinte.
- Barge-in WebRTC implantado durante `playback`, com 1,573 s de áudio pendente
  descartado, segundo turno completo e 140 frames audíveis recebidos no Windows.
- Serviço `0.7.0` ativo, health check aprovado e teste bem-sucedido sem erros.
- Validação física interrompeu uma resposta com 28,194 s de áudio pendente e iniciou
  corretamente um novo turno sobre Jesus.
- Segundo segmento de 2,54 s transcrito em 0,60 s; primeiro texto em 1,60 s e 23,61 s
  de voz sintetizados em 4,67 s, RTF `0,20`.

## [0.6.0] - 2026-09-26

### Added

- Silero VAD local para detectar início e fim da fala sem controle manual.
- `ConversationManager` independente do transporte, integrando STT, LLM e TTS.
- Histórico limitado por peer e contexto de múltiplos turnos na Responses API.
- Eventos SSE da conversa automática e modo correspondente na interface web.
- Download do modelo VAD com checksum e verificador de conversa implantada.

### Changed

- Versão publicada como `0.6.0`.
- Barge-in e transcrições parciais ficam explicitamente desabilitados até suas fases.

### Validated

- Quatorze testes no Windows e no Raspberry Pi ARM64.
- Modelo VAD carregado nos dois ambientes e pergunta portuguesa segmentada por silêncio.
- Dois turnos implantados na mesma sessão, com quatro mensagens no histórico ao final.
- Duas respostas TTS entregues por WebRTC, totalizando 463 frames audíveis no Windows.
- Validação física no navegador com segmentos automáticos de 5,00 s e 5,39 s; STT
  em 0,95 s e 1,03 s, ambos com RTF `0,19`.
- Primeiro texto em 1,32 s e 0,94 s; síntese local em 0,34 s nos dois turnos, com
  RTF `0,20` e `0,18`.
- Histórico da sessão avançando até o limite de 12 mensagens, encerramento normal
  do peer e serviço sem erros no journald.

## [0.5.0] - 2026-09-26

### Added

- Abstração substituível de TTS e voz Piper brasileira local via sherpa-onnx.
- Endpoint de síntese associado ao peer e envio do PCM por WebRTC ao navegador.
- Download do modelo com checksum, benchmark local e verificador TTS ao vivo.
- Interface web que reproduz automaticamente a resposta do assistente.

### Changed

- Versão publicada como `0.5.0`.
- O loopback passou a ser controlado no servidor para compartilhar a faixa de saída
  com a voz do assistente.

### Validated

- Onze testes no Windows e no Raspberry Pi ARM64.
- Modelo real gerou 3,036 s de voz em 0,707 s, RTF `0,233`.
- Implantação HTTPS gerou 3,882 s em 0,795 s, RTF `0,205`, e entregou 185 frames
  audíveis ao peer Windows por WebRTC.
- Serviço ativo, health check aprovado e ciclo TTS/WebRTC sem erros nos logs.
- Fluxo físico completo no navegador: STT de 5,50 s em 0,79 s, primeiro texto em
  0,97 s, resposta total em 1,13 s e 2,79 s de voz gerados em 0,56 s, RTF `0,20`.

## [0.4.0] - 2026-09-26

### Added

- Abstração substituível de LLM e adaptador para a OpenAI Responses API.
- Endpoint SSE que transmite deltas, primeiro token e tempo total ao navegador.
- Interface web que envia a transcrição e exibe incrementalmente a resposta.
- Verificador do streaming LLM contra uma implantação HTTPS real.

### Changed

- Versão publicada como `0.4.0`.
- Modelo padrão configurado como `gpt-6-luna`, com saída limitada a 300 tokens.
- Instrução padrão solicita texto simples sem Markdown para a interface e o futuro TTS.

### Validated

- Nove testes no Windows e Raspberry Pi ARM64.
- Chamada real local e endpoint HTTPS implantado, com primeiro texto em `1,520 s` e
  conclusão em `1,683 s`.
- Fluxo físico de voz até resposta validado: STT de 7,08 s em 0,98 s, RTF `0,14`,
  primeiro texto em 1,97 s e conclusão em 2,85 s.
- Resposta final sem Markdown validada na implantação `0.4.0`.

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
