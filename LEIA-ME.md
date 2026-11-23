# Biblioteca InfoLivros

Extraia sobre a pasta anterior para reaproveitar os PDFs, os índices e o ambiente Windows Python 3.14. Execute uma operação por vez.

| Ambiente | Janela | Terminal com download e conferência |
|---|---|---|
| Windows com Python 3.14 | ABRIR-INTERFACE.cmd | py -3.14 acervo.py completo |
| Linux com Python 3.9+ | sh iniciar.sh gui | sh iniciar.sh completo |

No Debian, Ubuntu ou Mint, se faltarem Tk ou venv, instale com `sudo apt install python3-tk python3-venv`. A interface precisa de uma sessão gráfica. No servidor via SSH use os comandos de terminal.

Outras operações de terminal: links, baixar, conferir e renomear. Consulte acervo.py --help.
O modo auto detecta NVIDIA com nvidia-smi e testa o CUDA. Se a preparação CUDA falhar, prossegue com extração de texto. Use --modo cuda para exigir GPU ou --modo cpu para leitura de texto. O OCR é usado no modo CUDA quando o texto extraído não basta. A primeira conferência instala as dependências no ambiente virtual da pasta.

Os PDFs ficam em dados/pdfs, o ZIP em resultado/InfoLivros.zip e a conferência em conferencia-titulos.csv. O relatório distingue títulos confirmados, divergências de conteúdo e itens a revisar. O coletor usa os cartões e as categorias específicos do InfoLivros.

## Pastas e duplicatas

A organização escolhida vale para dados/pdfs e para o ZIP criado. Use --pastas categoria (padrão), tema (categoria e subtema) ou unica. Para aproveitar livros anteriores sem acessar a internet, selecione Reorganizar PDFs locais, ou rode acervo.py organizar --pastas tema. A classificação usa a página de origem registrada em resultado*/links.csv. Arquivos avulsos sem registro ficam onde estão. Uma URL presente em várias seções recebe a primeira origem registrada.

Selecione Analisar duplicatas e consulte duplicatas.csv. As linhas mostram as duas localizações, bytes, contagem de páginas quando legível e o SHA-256 das cópias idênticas. Nomes normalizados semelhantes com conteúdo diferente exigem revisão. Excluir cópias idênticas refaz a comparação, atualiza o índice e reconstrói ZIPs existentes. No terminal use acervo.py duplicatas e depois acervo.py limpar --confirmar-exclusao. Execute uma operação de cada vez.

### Usar uma pasta escolhida manualmente

Na janela principal clique em **Organizar uma pasta…** e depois em **Escolher pasta…**. A lista inclui os PDFs das subpastas. Use Ctrl ou Shift para selecionar vários. Em **Mover seleção…**, digite uma subpasta como História/Brasil. Se já existir um arquivo com o mesmo nome, o programa adiciona um número ao nome do PDF movido. A análise escreve duplicatas-infolivros.csv na pasta escolhida. A exclusão exige confirmação e revalida o conteúdo.

No Windows: `py -3.14 manual.py duplicatas --pasta "D:\\Livros"`. Para organizar: `py -3.14 manual.py mover --pasta "D:\\Livros" --destino "História/Brasil" --arquivos "Livro A.pdf" "Livro B.pdf"`. No Linux, use python3 no lugar de py -3.14.

## Procurar PDFs em vários sites

Selecione **Buscar PDFs em sites… → Iniciar**. Edite as URLs (uma por linha), depois clique em **Salvar e baixar**. O exemplo inicial é o catálogo InfoLivros. **Salvar lista** também aceita a lista vazia. A lista é guardada em sites.json. Os limites valem para a execução atual.

No terminal: `py -3.14 acervo.py sites --site https://exemplo.org/biblioteca/ --site https://outro.org/livros/ --limite 100 --profundidade 3`. Use python3 no Linux. Sem --site o comando utiliza a lista salva.

Cada execução gera uma nova pasta em resultado-sites. Os PDFs são agrupados pelo domínio de entrada, com links.csv, pendencias.csv e um PDFs.zip quando houver downloads válidos. A busca lê links públicos no HTML, admite links diretos a PDFs externos e visita páginas internas até o limite. Páginas renderizadas exclusivamente por JavaScript, áreas com login e visualizadores sem link público podem exigir integração própria. Os nomes vêm do texto do link ou do endereço. O fluxo específico **Baixar e conferir** e o BAIXAR-TUDO.cmd continuam disponíveis para a conferência interna e a organização por categoria do InfoLivros.

## Sobre o Foliúme

Feito por olverlock em 22/11/2026 18:36

Interface: Ajuda → Sobre o Foliúme. Terminal: `acervo.py sobre` com o interpretador Python.
