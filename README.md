# Foliúme

<p align="center"><img src="foliume.png" alt="Foliúme — livro aberto em verde-petróleo com um detalhe âmbar" width="420"></p>

**Encontre PDFs públicos, confira a origem dos livros e organize sua biblioteca local.** O Foliúme reúne três fluxos em um aplicativo Python com interface gráfica em português e comandos para Windows e Linux.

| Quero… | Por onde começar |
|---|---|
| Buscar PDFs em um ou vários sites | **Buscar PDFs em sites…** |
| Baixar o catálogo InfoLivros com categorias e conferir o título dentro de cada PDF | **Baixar e conferir** |
| Organizar livros que já estão no meu disco | **Organizar uma pasta…** |

[Primeiros passos](#primeiros-passos) · [Busca em vários sites](#busca-em-vários-sites) · [Conferência de títulos](#conferência-de-títulos) · [Duplicatas](#duplicatas) · [Terminal](#terminal) · [Solução de problemas](#solução-de-problemas)

## Primeiros passos

Baixe o código pelo botão **Code → Download ZIP** do GitHub e extraia em uma pasta onde você possa gravar arquivos. Nas atualizações, extraia sobre a pasta existente para reaproveitar os PDFs, os índices e a lista de sites. Execute uma operação por vez sobre a mesma biblioteca.

| Ambiente | Requisitos | Abrir o aplicativo |
|---|---|---|
| Windows | Python **3.14** de 64 bits, com o inicializador `py` e Tkinter | Duplo clique em `ABRIR-INTERFACE.cmd` |
| Linux com desktop | Python 3.9+, Tkinter e sessão gráfica | `sh iniciar.sh gui` |
| Linux via SSH | Python 3.9+. A conferência e a análise de duplicatas também usam `venv` e dependências compatíveis com a arquitetura | `sh iniciar.sh --help` |

No Debian, Ubuntu ou Linux Mint, se faltarem os componentes de interface ou de ambiente virtual:

```bash
sudo apt install python3-tk python3-venv
```

**Primeiro teste:** abra a interface, escolha **Buscar PDFs em sites… → Iniciar** e cole a URL de uma página que contenha um link público para PDF. Use **1 página** e **profundidade 0** para testar somente essa página e seus links diretos de download. Clique em **Salvar e baixar**. O registro exibe a pasta do resultado ao concluir.

## Busca em vários sites

A lista começa com o catálogo InfoLivros. Você pode trocar o exemplo, apagá-lo ou inserir vários endereços, um por linha. **Salvar lista** guarda as URLs em `sites.json`. **Salvar e baixar** inicia a busca. Cada execução cria uma pasta própria em `resultado-sites/`.

- **Limite** controla quantas páginas o coletor pode visitar por endereço inicial. O padrão é 100.
- **Profundidade** controla quantos níveis de links internos pode seguir. O padrão é 3. Links diretos para PDFs podem apontar para outro domínio.
- **Resultado** inclui os PDFs por domínio de entrada, a relação de links, as pendências e um ZIP quando houver downloads válidos.
- **Cobertura** depende dos links encontrados no HTML público. Login, visualizadores proprietários e páginas que só exibem links após executar JavaScript podem exigir uma integração específica.

O modo multissite obtém o nome do documento a partir do texto do link ou do endereço. A conferência de títulos descrita abaixo pertence ao fluxo dedicado ao InfoLivros.

## Catálogo InfoLivros

Selecione **Baixar e conferir** para percorrer o catálogo, reaproveitar PDFs já baixados, criar o ZIP e conferir os arquivos. No Windows, `BAIXAR-TUDO.cmd` também inicia esse fluxo. O ZIP é gerado **antes da conferência** e inclui os PDFs baixados, inclusive os que depois receberem indicação de revisão.

| Organização | Exemplo dentro de `dados/pdfs/` |
|---|---|
| Pasta única | `Livro.pdf` |
| Por categoria | `matematica/Livro.pdf` |
| Categoria e tema | `matematica/algebra/Livro.pdf` |

Para classificar um acervo já baixado, use **Reorganizar PDFs locais**. A operação consulta a página de origem registrada em `resultado*/links.csv`. **Renomear PDFs antigos** utiliza esse índice para identificar arquivos de versões anteriores que tinham códigos no nome.

### Conferência de títulos

O verificador consulta a página atual do InfoLivros, associa o título ao link de download, calcula o SHA-256 da cópia local e do PDF servido pelo site e procura o título nas **três primeiras páginas**. A conferência transfere novamente o conteúdo remoto para calcular o hash. Considere esse consumo de rede ao verificar acervos grandes.

| Resultado em `conferencia-titulos.csv` | Interpretação |
|---|---|
| `CONFIRMADO` | Os hashes coincidiram e o título do catálogo foi encontrado no PDF segundo o critério do verificador. Consulte a página e o trecho registrados. |
| `DIVERGENTE` | Os hashes diferem. O site pode ter atualizado o arquivo desde o download. |
| `REVISAR` | A evidência foi insuficiente. Consulte o motivo, como título de uma palavra, falta de texto reconhecível ou indisponibilidade da origem. |

### CPU e OCR com NVIDIA

O modo **CPU** extrai o texto selecionável usando pypdfium2. O modo **CUDA** acrescenta OCR com EasyOCR e PyTorch quando a leitura direta é insuficiente. No modo **Automático**, o aplicativo procura a GPU com `nvidia-smi`, prepara o ambiente e testa uma operação CUDA. Se a preparação ou o teste inicial falhar, tenta a leitura direta na CPU.

Na primeira utilização, o programa pode baixar bibliotecas e modelos. Os ambientes Python ficam na pasta do aplicativo. O instalador de GPU usa o índice PyTorch CUDA 12.8. A disponibilidade depende do driver, da versão do Python e dos pacotes publicados para a plataforma.

## Organização manual

Em **Organizar uma pasta… → Escolher pasta…**, selecione a pasta real dos seus PDFs, inclusive livros obtidos fora do InfoLivros. A lista inclui as subpastas. Selecione um ou mais PDFs com **Ctrl** ou **Shift**, clique em **Mover seleção…** e informe uma categoria como `História/Brasil`. O programa cria o destino e acrescenta um número ao nome se já existir um arquivo com aquele nome.

### Duplicatas

**Analisar duplicatas** gera um CSV com os caminhos comparados, o tamanho em bytes e o número de páginas quando legível. A análise pode detectar cópias idênticas mesmo que os nomes sejam diferentes.

- **IDÊNTICO** exige tamanho igual, SHA-256 igual e comparação byte a byte.
- **REVISAR** agrupa candidatos com nomes equivalentes após normalização e conteúdo diferente. Podem ser edições distintas.
- **Excluir cópias idênticas** exige confirmação e refaz a comparação antes da exclusão. Leia a coluna **Manter** para saber qual exemplar será preservado. A exclusão remove o arquivo do disco.

O relatório do acervo gerenciado é `duplicatas.csv`. Na análise manual de uma pasta externa, procure `duplicatas-infolivros.csv` dentro da pasta escolhida.

## Terminal

Execute os comandos na pasta que contém `acervo.py`. Os exemplos abaixo usam o Windows. No Linux, substitua `py -3.14` por `python3`.

```powershell
# Visitar o catálogo com um limite pequeno
py -3.14 acervo.py sites --site https://infolivros.org/livros-pdf-gratis/ --limite 10 --profundidade 2

# Baixar o catálogo dedicado, separar por tema e conferir os títulos
py -3.14 acervo.py completo --pastas tema --modo auto

# Procurar duplicatas em uma pasta escolhida no disco
py -3.14 manual.py duplicatas --pasta "D:\Livros"

# Mover dois PDFs para a mesma categoria
py -3.14 manual.py mover --pasta "D:\Livros" --destino "História/Brasil" --arquivos "Livro A.pdf" "Livro B.pdf"
```

| Operação com `acervo.py` | Resultado |
|---|---|
| `gui` | Abre a interface. É a ação padrão quando você omite a operação. |
| `sites` | Usa os endereços salvos. Repita `--site URL` para informar vários na mesma execução. |
| `links` | Coleta os links do catálogo InfoLivros. |
| `baixar` / `completo` | Baixa e cria o ZIP. O segundo comando também executa a conferência. |
| `conferir` | Confere os PDFs do acervo gerenciado com o site e o conteúdo interno. |
| `organizar` / `renomear` | Reorganiza por pasta ou recupera os nomes de arquivos antigos. |
| `duplicatas` / `limpar` | Analisa duplicatas ou exclui cópias idênticas. Para excluir pelo terminal, acrescente `--confirmar-exclusao`. |
| `sobre` / `--help` | Exibe a autoria ou a ajuda de uso. |

**Opções:** `--pastas unica|categoria|tema` escolhe o layout do acervo InfoLivros. `--modo auto|cpu|cuda` escolhe o modo de conferência. Para arquivos externos, `manual.py --help` descreve as ações `listar`, `mover`, `duplicatas` e `limpar`.

## Onde estão meus arquivos?

| Caminho relativo à pasta do programa | Conteúdo |
|---|---|
| `dados/pdfs/` | PDFs do catálogo dedicado, organizados conforme sua escolha |
| `dados/nomes.json` | Associação entre URL e caminho local usada para reencontrar os livros |
| `resultado/InfoLivros.zip` | Acervo baixado do catálogo InfoLivros |
| `resultado/links.csv` e `resultado/pendencias.csv` | Origens dos livros e falhas do coletor dedicado |
| `conferencia-titulos.csv` | Resultado da conferência, hashes e evidências de leitura disponíveis |
| `resultado-sites/<execução>/` | PDFs por site, `links.csv`, `pendencias.csv` e `PDFs.zip` quando aplicável |
| `sites.json` | Lista editável salva pela interface multissite |

## Solução de problemas

| Sintoma | O que verificar |
|---|---|
| Windows informa que o Python solicitado está ausente | Execute `py -0p` para listar as instalações e `py -3.14 --version` para verificar o interpretador usado pelos atalhos. |
| A janela não abre no Linux | Verifique se há uma sessão gráfica e se o Tkinter está instalado. Por SSH, use diretamente uma operação como `sh iniciar.sh links`. |
| A busca encontra poucos PDFs | Abra `pendencias.csv`. Confira se a URL inicial é a do catálogo, se a página contém links públicos e se os limites de navegação foram atingidos. |
| O arquivo está no ZIP, mas o título ficou em revisão | Consulte o motivo no CSV de conferência. Em um PDF escaneado, o OCR pode encontrar um título que a extração direta não conseguiu ler. |
| O disco ficou sem espaço | Os PDFs individuais e o ZIP coexistem. Reserve espaço para ambos e, ao usar GPU, para os pacotes e modelos de OCR. |

## Autoria

**Feito por olverlock em 22/11/2026 18:36**

O crédito também está disponível em **Ajuda → Sobre o Foliúme** e pelo comando `acervo.py sobre`.
