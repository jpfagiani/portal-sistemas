# Portal Interno da Unidade

Painel inicial da unidade: menu lateral fixo, banner rotativo e cartões com
comunicados, acesso rápido aos sistemas, atalhos úteis, aniversariantes do mês,
ramais mais usados, escalas do dia, chamados de TI e reservas rápidas.

Os cartões ficam **sempre no mesmo lugar**, mesmo vazios, para a página não
mudar de forma conforme vai sendo preenchida. Cada um mostra um número máximo
de itens; passando disso, aparece um **"Ver todos"** que abre a lista completa
em outra aba.

A página é **aberta a quem estiver na rede** — ninguém precisa de senha para
consultá-la. O login existe apenas para o **gerenciamento**: quem entra como
administrador altera os botões, o banner, os avisos, a aparência e os usuários,
tudo dentro do próprio site, sem mexer em arquivo nenhum.

Feito para **Debian 13 (trixie)**; o instalador também aceita Debian 12 e,
em versões mais antigas, monta um ambiente virtual automaticamente.

## Instalação

Clone em `/opt/portal-sistemas`: o portal roda a partir da própria pasta do clone, então
`git pull` seguido de `atualizar.sh` atualiza o que está no ar.

```bash
sudo git clone https://github.com/jpfagiani/portal.git /opt/portal-sistemas
cd /opt/portal-sistemas
sudo ./instalar.sh            # porta 80
# ou: sudo ./instalar.sh 8080
```

O instalador é interativo e pergunta tudo o que muda de uma unidade para outra
— **nenhum arquivo precisa ser editado à mão**:

1. **Sistema**: confere a versão do Debian e escolhe os pacotes certos para ela
   (`python3-flask` e `gunicorn` do repositório oficial no 12/13; venv + pip
   nas versões antigas).
2. **Identidade da unidade**: nome que aparece no cabeçalho, sigla e subtítulo,
   com confirmação antes de seguir. É o que permite outra unidade usar o mesmo
   código sem alterar nada.
3. **Acesso do administrador**: o portal começa com um único usuário, de login
   fixo `admin`, e você digita a senha dele aqui (com confirmação; mínimo de 8
   caracteres, com maiúscula, minúscula e número — mesma exigência do portal do
   Samba). Nada de senha padrão no código, e nenhuma senha impressa na
   tela ao final. Os demais logins são criados depois em *Administração →
   Usuários*.
4. **Rede**: lista as placas detectadas (IP, estado e MAC), sugere a que está
   em uso, **pede confirmação e deixa escolher outra**. Depois oferece manter a
   configuração, definir IP fixo (endereço, máscara, gateway e DNS, com uma
   revisão final antes de aplicar) ou usar DHCP. Detecta se quem comanda a rede
   é o NetworkManager e usa `nmcli` nesse caso, ou `ifupdown` no caso contrário.
   **Este passo é pulado quando existe `/etc/gwos/gwos.conf`**: ali o gateway
   GWOS é o dono da rede, e uma segunda definição da mesma placa faria o `ifup`
   falhar no próximo boot. Para trocar o IP nessa máquina use `sudo gwos ip`.
   Por fim pergunta o **nome de acesso** (ver abaixo).
5. **Dependências**: instala os pacotes.
6. **Arquivos**: prepara `/opt/portal-sistemas` e pergunta os caminhos do **logo** e da
   **foto de fundo** (opcional — dá para fazer depois pelo painel ou trocando o
   arquivo). Clonado direto em `/opt/portal-sistemas`, nada é copiado: o serviço roda
   da própria pasta. Numa reinstalação, o logo e a foto já instalados são
   preservados.
7. **Serviço** systemd `portal` (inicia no boot, reinicia se cair).
8. **Firewall**: libera a porta, se houver `ufw`.

No fim ele mostra o endereço de acesso. Entre com `admin` e a senha que você
definiu no passo 3.

> A configuração de rede faz **backup** de `/etc/network/interfaces` antes de
> qualquer alteração e, se o gateway não responder depois de aplicar, **desfaz
> sozinha** e volta ao que era. Ainda assim, prefira rodar pelo console físico:
> se você estiver por SSH, a conexão cai quando o IP muda.

### Menu lateral

Os itens do menu são cadastrados em *Blocos do painel → Menu lateral*. Cada um
tem nome, ícone e um endereço opcional:

- **sem endereço** — abre a página "módulo em preparação" (útil para reservar o
  espaço de algo que ainda vai existir);
- **com endereço interno** (`/ramais`) ou **externo** — leva direto ao destino.

Desmarcar *Exibir* esconde o item sem apagá-lo, e a ordem se muda arrastando.

## Acesso por nome, sem servidor DNS

O instalador pergunta o endereço que as pessoas vão digitar (por exemplo
`cdpni.local`). Terminando em **`.local`**, o próprio servidor passa a anunciar
o nome na rede por **mDNS** — a unidade **não precisa ter servidor DNS**.

Windows 10 (1703 em diante), Windows 11, macOS, Linux e celulares resolvem
`.local` sem instalar nada. Teste de qualquer máquina da rede:

```
ping cdpni.local
```

Como funciona: o instalador instala o `avahi-daemon` e cria o serviço
`portal-nome`, que anuncia o nome apontando para o IP atual do servidor. O
hostname da máquina **não** é alterado — mexer nele poderia quebrar outros
serviços, como o Samba.

| Comando (no servidor) | Para quê |
|---|---|
| `systemctl status portal-sistemas-nome` | Ver a situação do anúncio |
| `avahi-resolve -n cdpni.local` | Testar a resolução |
| `systemctl restart portal-sistemas-nome` | Reanunciar — use depois de trocar o IP |

Limites, por desenho do protocolo: o mDNS vale **dentro da mesma rede/segmento**
e não atravessa roteador — em outra sub-rede o nome não resolve, e ali se usa o
IP. Usa UDP 5353, então switches ou firewalls que bloqueiem multicast impedem a
resolução. Windows 7 e anteriores precisariam do Bonjour instalado.

Nomes **fora de `.local`** (como `algo.sap.sp.gov.br`) não funcionam por mDNS:
dependem do DNS que responde por aquele domínio — no caso de um domínio do
governo, é o setor de TI da Secretaria que precisa criar um registro A. Se a
unidade tiver um DNS próprio (por exemplo o gateway GWOS), o nome também pode
ser publicado lá com `gwos dns add`; os dois métodos convivem sem conflito.

## Administração

O botão **Administração**, no canto superior direito, leva à tela de login. Entre
com `admin` (ou outro usuário administrador criado depois) para abrir o painel:

| Aba | O que faz |
|---|---|
| Sistemas e atalhos | Três abas — *Acesso rápido*, *Atalhos úteis* e *Reservas rápidas* — cada uma com sua própria lista, cadastro individual e importação por colagem. A ordem se muda **arrastando as linhas** |
| Banner | Imagens que passam automaticamente, com título, texto e link |
| Comunicados | Avisos do painel, com destaque (Urgente / Comunicado / Informação) e data |
| Blocos do painel | Menu lateral, chefia de plantão, escalas de hoje, aniversariantes do mês e chamados de TI |
| Ramais | Lista de telefones internos: item a item ou colando a lista inteira. Marque *destaque* para escolher quais aparecem no painel — sem nenhum marcado, ele mostra os primeiros da lista |
| Usuários | Criar logins, trocar senhas, desativar e definir quem é administrador |
| Aparência | Foto de fundo, nome da unidade, cores e tempo de cada slide |

### Logo e foto de fundo

As duas imagens da identidade são **arquivos soltos** em
`/opt/portal-sistemas/static/` — trocar o arquivo troca o site, sem mexer no código e
sem reiniciar o serviço:

| Arquivo | O que é |
|---|---|
| `logo.png` *(ou .jpg/.webp/.svg)* | Logo da unidade — cabeçalho, tela de login e ícone da aba |
| `fundo.jpg` *(ou .png/.webp)* | Foto aérea usada como fundo do site |
| `brasao.png` | Logo padrão que acompanha o repositório; só é usado se não houver `logo.*` |
| `marca-aniversarios.*` | Marca d'água do cartão de aniversariantes (um bolo, por padrão) |

```bash
sudo cp minha-logo.png  /opt/portal-sistemas/static/logo.png
sudo cp minha-foto.jpg  /opt/portal-sistemas/static/fundo.jpg
sudo chown portal-sistemas:portal-sistemas /opt/portal-sistemas/static/logo.png /opt/portal-sistemas/static/fundo.jpg
```

O mesmo pode ser feito pelo painel, em *Aparência* — os dois caminhos gravam nos
mesmos arquivos. O endereço das imagens leva a data do arquivo
(`logo.png?v=...`), então o navegador dos usuários busca a versão nova em vez de
mostrar a antiga do cache.

Sem foto de fundo, o portal usa um degradê com as cores institucionais.
Resolução recomendada para o fundo: **1920×1080 ou maior** — fotos pequenas
ficam borradas ao serem esticadas para o tamanho da tela.

Cuidados embutidos: não é possível excluir o próprio usuário nem remover o
último administrador — isso evita ficar trancado para fora do painel.

## Atualizar

Para trazer uma versão nova do código sem perder nada:

```bash
git pull
sudo ./atualizar.sh
```

Copia apenas `app.py`, os templates e o CSS/JS, e reinicia o serviço. Banco de
dados, imagens enviadas, logo, foto de fundo e configurações ficam intactos.

## Operação

```bash
systemctl status portal-sistemas       # situação do serviço
journalctl -u portal-sistemas -f       # logs em tempo real
sudo systemctl restart portal-sistemas # reiniciar
```

### Esqueceu a senha?

Não há senha padrão, e reinstalar **não ajuda**: o instalador detecta o banco
existente e preserva os usuários — a senha antiga continua sendo a antiga.

```bash
sudo ./redefinir_senha.sh          # lista os usuários e pergunta qual
sudo ./redefinir_senha.sh admin    # direto para um usuário
sudo ./redefinir_senha.sh listar   # só lista, sem trocar nada
```

Mesma exigência de senha do instalador (8 caracteres, maiúscula, minúscula e
número). Reativa a conta se estiver desativada — trocar a senha de um usuário
inativo sem isso pareceria que o reset não funcionou.

Backup: copie `/opt/portal-sistemas/dados.db` (usuários e conteúdo) e a pasta
`/opt/portal-sistemas/static/uploads` (imagens).

```bash
sudo tar czf portal-backup-$(date +%F).tgz -C /opt/portal-sistemas dados.db static/uploads
```

## Desinstalar

```bash
sudo ./desinstalar.sh    # remove o serviço; PRESERVA dados e imagens
```

## Segurança

- Restaurar um backup de uma versão anterior é seguro: o banco é atualizado
  na hora, sem precisar reiniciar o serviço.
- A página inicial é pública dentro da rede: **não publique nela nada que não
  possa ser visto por qualquer pessoa com acesso à rede da unidade.**
- O gerenciamento (`/admin/...`) exige login com perfil de administrador.
- Senhas guardadas com hash (PBKDF2, via Werkzeug) — nunca em texto puro.
- Formulários protegidos contra CSRF; uploads limitados a 16 MB e às extensões
  PNG, JPG, WEBP e GIF.
- Sem HTTPS por padrão: é um portal de **rede interna**. Para expor fora da LAN,
  coloque um proxy reverso (nginx) com certificado na frente.

## Estrutura

| Caminho | Papel |
|---|---|
| `app.py` | Aplicação Flask: login, página inicial e administração |
| `templates/` | Páginas HTML (Jinja2) |
| `static/style.css` | Estilo — azul institucional com o dourado do brasão |
| `static/logo.*`, `static/fundo.*` | Identidade visual da unidade (trocáveis por arquivo) |
| `static/banner.js` | Rotação automática do banner |
| `instalar.sh` / `desinstalar.sh` | Instalação e remoção no Debian |
| `dados.db` | Banco SQLite (criado na primeira execução, fora do Git) |
