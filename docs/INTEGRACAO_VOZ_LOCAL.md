# Nova interface com a voz do Jarvis pessoal

JARVIS é o aplicativo principal. A home abre **Agentes**; o GGO fica dentro
desse catálogo como uma especialidade. O título da janela permanece JARVIS.

A nova home LED pode usar a mesma entrada de microfone do `main.py` original.
O preparador cria outra pasta, troca a ponte de áudio **somente nessa cópia** e
acrescenta os seis arquivos da interface. O `main.py`, a janela nativa, os
provedores de voz e os scripts GGO continuam presentes. A janela nativa ainda
controla as configurações, o mudo e a saída de voz; a nova home abre no navegador.
Esta etapa não substitui a janela PyQt inteira.

## Atualizar a cópia já testada e criar o iniciador

Se a preparação anterior já mostrou `COPIA PREPARADA`, feche a instância do
Jarvis e sua tela de microfone. Baixe novamente o ZIP da branch
`codex/integracao-voz-interface`, extraia em uma pasta nova e abra o PowerShell
na pasta do `README.md`. Execute:

```powershell
python .\tools\atualizar_interface_local.py --pasta "$env:USERPROFILE\Desktop\Jarvis-Teste" --atalho
```

O atualizador confere os hashes existentes, guarda backup local da interface e
substitui apenas a ponte e os seis arquivos públicos. `main.py`, configurações,
memórias, scripts GGO e a origem não entram na lista de escrita. Edições pessoais
na interface são recusadas para revisão; repetir uma atualização idêntica não
reescreve os arquivos. Falhas de escrita revertem os arquivos já substituídos;
o backup permanece disponível para revisão.

O Desktop real do Windows recebe **Jarvis - Interface nova.cmd**. Duplo clique
inicia o mesmo Python usado no preparo, com o diretório correto. O `main.py`
continua sendo o ponto de entrada e abre a nova tela quando o provedor conecta.
O iniciador usa o Edge instalado para abrir uma janela própria sem barra de
endereço; se o Edge não estiver disponível, usa o navegador padrão. Não há nova
instalação nem alteração global de configuração. A janela nativa da voz ainda
fica disponível; a interface web não foi embutida no PyQt.

Para criar apenas o iniciador após uma preparação nova:

```powershell
python .\tools\criar_atalho_local.py --pasta "$env:USERPROFILE\Desktop\Jarvis-Teste"
```

O criador nunca inicia o aplicativo, não substitui um iniciador de conteúdo
diferente e respeita Desktop redirecionado. O `.cmd` deixa a mensagem visível se
o aplicativo terminar com erro. Fechar apenas a tela nova encerra a captura;
para desligar o aplicativo, feche também a janela nativa.

O arquivo original recebido foi inspecionado como referência, sem executar o
aplicativo. Seus 269 arquivos foram preservados e verificados por SHA-256 na
preparação local de revisão. Nenhum conteúdo desse ZIP, configuração pessoal,
memória, imagem operacional ou chave foi adicionado ao GitHub. O único código
publicado é o novo adaptador, preparador, interface, documentação e testes.

## Preparar no Windows, sem instalar Node, Git ou PowerShell 7

Use o Python que já abre seu Jarvis. O preparador precisa de Python 3.11 ou
superior e usa apenas a biblioteca padrão. Ele não instala dependências nem
inicia programas. A execução posterior do Jarvis requer as mesmas dependências
Python e configurações que sua instalação atual já utiliza.

1. Baixe a branch `codex/integracao-voz-interface` do GitHub em **Code → Download
   ZIP** e extraia em outra pasta. Abra o PowerShell nessa pasta, onde estão
   `README.md`, `tools` e `interface-oficial`.
2. Execute o comando abaixo. O destino deve ser uma pasta nova, fora de qualquer
   checkout Git. Se `Jarvis-Teste` já existir, escolha outro nome; o preparador
   nunca sobrescreve uma cópia anterior.

```powershell
python .\tools\preparar_interface_local.py --origem "C:\Users\bruno.lsouza\Downloads\Jarvis_Etapa4_Base_Segura\Jarvis" --destino "$env:USERPROFILE\Desktop\Jarvis-Teste" --corrigir-datas
```

A origem precisa ser a pasta que contém seu `main.py`. Se o ZIP foi extraído com
mais uma pasta intermediária, ajuste apenas `--origem`. O destino também pode
ser outra pasta pessoal nova, caso seu Desktop esteja redirecionado.

O sucesso mostra `COPIA PREPARADA`, `PASTA ORIGINAL PRESERVADA` e
`NENHUM APLICATIVO EXECUTADO`. Com `--corrigir-datas`, também aparecem
`LEITURA DAS DATAS CORRIGIDA` e `CODIGO VALIDADO`: o configurador na cópia ganha
cinco tentativas de leitura, com backup byte a byte. **Nenhuma data é preenchida
e nenhum processamento é iniciado.** Sem essa opção, o configurador é copiado
sem alterações.

O preparador recusa uma versão diferente da ponte analisada, links/junctions,
pastas sobrepostas, destino existente, destino dentro de Git, metadados Git na
origem ou uma integração já presente. Falhas de cópia deixam o destino com
marcador `incompleto`; não execute essa pasta nem reutilize seu nome. A origem
permanece intacta. O manifesto privado `.jarvis-interface.json` registra hashes,
nunca valores de configurações.

## Testar a nova cópia

Feche a instância anterior do Jarvis e a antiga aba de microfone para liberar a
porta 8765. Não é necessário encerrar a prévia visual da porta 8790, mas ela não
conecta a voz. Depois de confirmar o sucesso do preparador:

```powershell
Set-Location "$env:USERPROFILE\Desktop\Jarvis-Teste"
python .\main.py
```

O fluxo original só inicia a ponte depois que o provedor de voz conecta. Assim,
a configuração de API/voz na janela nativa continua necessária. Se a aba não
abrir, acesse **http://127.0.0.1:8765/** depois que a janela indicar a conexão.
Use esse endereço exato; `localhost` e outras origens são recusados pela ponte.

Na home nova, clique em **Ativar microfone** e permita o acesso no Edge. Não há
pedido de microfone ao carregar a página. O círculo mostra **Ouvindo** somente
quando a captura a 48 kHz está ativa e o servidor confirmou a conexão. Isso
confirma o transporte do microfone; não confirma uma resposta do modelo.

1. Fale uma frase pessoal simples, sem dados de trabalho, e confira se o Jarvis
   ouve e responde pela saída configurada na janela nativa.
2. Ative/desative o mudo na janela nativa: a nova tela deve acompanhar e suspender
   o envio de áudio enquanto estiver silenciada.
3. Abra **Agentes → GGO** ou Configurações e use **Parar microfone** no cabeçalho. A captura deve
   encerrar também ao fechar a aba ou perder a conexão, sem reconexão automática.
4. Engenharia e Controladoria continuam mostrando **Não configurado**. Não
   execute DUX, Excel ou processamento GGO nesse teste.

**Parar microfone** encerra a captura no navegador e não altera a preferência de
mudo da janela nativa. Ao parar, **Encerrando microfone** aparece até o dispositivo
e a conexão terminarem; só depois **Ativar microfone** é liberado. Reative e
confira uma nova resposta. Se a liberação exceder cinco segundos, a tela mostra
erro e pede atualização da página, sem iniciar outra captura sobre a anterior.

Se a tela mostrar **Ouvindo** sem resposta, confira também os controles originais
de wake word/PTT na janela nativa. Abrir o microfone não desperta automaticamente
um assistente configurado para aguardar a palavra de ativação.

O áudio passa pelo callback original do Jarvis, que preserva suas regras de
mudo, wake word, PTT e eco. O provedor configurado no aplicativo pode processá-lo
online. A ponte não adiciona reconhecimento de fala ou envio para outra API.
Os estados visuais de processando/respondendo continuam disponíveis na prévia
estática; no modo integrado não são simulados como se fossem estado do modelo.

Se aparecer erro, envie somente a mensagem visível, sem configurações ou chaves.
Não envie a pasta `Jarvis-Teste` ao GitHub: ela contém suas configurações locais.
O atalho de Desktop oferecido pelo Jarvis original aponta para o `main.py` da
instalação em que foi criado; não muda automaticamente para esta cópia.

## Verificação de desenvolvimento e limites

```sh
python -m pip install -r requirements-test-voz.txt
python -m unittest discover -s tests -v
npm ci --ignore-scripts
npx playwright install chromium
npm test
```

Os testes Python incluem preparação em árvores sintéticas, integridade dos
originais, Etapa 201, PowerShell e a ponte FastAPI em memória. Os testes de UI
mantêm navegação/acessibilidade e simulam permissão, AudioContext e WebSocket
sem acessar um microfone real. A suíte PowerShell requer `pwsh` e Git; Node é
necessário apenas para os testes automatizados, não para abrir a interface.

Também foi validado em Chromium o caminho completo de um microfone **fictício**
do navegador, passando por WebSocket real até o callback PCM16: pelo menos
32.768 bytes recebidos, interrupção no mudo e parada após navegar, sem erros JS.
Também passaram cinco ciclos completos de ativar, navegar e parar/reativar,
com áudio fictício pela conexão real e sem erros JavaScript. O encerramento
assíncrono lento e seu timeout têm testes determinísticos adicionais.
Nenhum `main.py` original, provedor de IA, DUX ou Excel foi executado na nuvem.
A audição, resposta de voz e o dispositivo de saída reais ainda dependem do teste
manual no Windows. A Etapa 201 continua pendente de validação operacional.

A conversão mantém o formato da ponte anterior: Float32 mono 48 kHz para PCM16
mono 16 kHz, agora preservando as amostras entre quadros. Quadros inválidos,
origens diferentes e uma segunda aba capturando são recusados. Apenas os seis
arquivos da interface são servidos; a pasta pessoal nunca é exposta por HTTP.
O cliente usa `ScriptProcessorNode`, compatível com a base recebida e atualmente
obsoleto nos navegadores; sua migração futura para AudioWorklet pode ser feita
sem alterar o callback original.

## Voltar à versão anterior

Feche a nova aba e a instância da cópia. Abra o `main.py` na pasta original ou
use seu atalho anterior. Nenhuma restauração da origem é necessária. Os backups
`browser_audio_bridge_antes_interface.py` e, se solicitado,
`jarvis_configurar_datas_controladoria_antes_correcao.py` ficam somente na nova
cópia para revisão. Nenhum merge ou publicação de ambiente é feito pelo preparo.
