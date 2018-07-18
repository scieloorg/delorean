DeLorean
========

Geração de bases ISIS (formato ID), com base em dados
obtidos via API do Journal Manager (gerenciador de catálogo
do SciELO periódicos).


.. image:: https://secure.travis-ci.org/scieloorg/delorean.png?branch=master
`See Build details <http://travis-ci.org/#!/scieloorg/delorean>`_

Instalação
----------

**Atenção: esta aplicação só pode ser executada em Python 2.7.x**

A aplicação deve ser obtida por meio do `repositório de códigos
<https://github.com/scieloorg/delorean>`_ das seguintes formas:

Clonagem do repositório git::

    git clone https://github.com/scieloorg/delorean.git


Download do conteúdo do repositório em um pacote zipado::

    https://github.com/scieloorg/delorean/archive/master.zip


Edite o arquivo *production.ini* para definir os valores das diretivas
``delorean.manager_access_username`` e ``delorean.manager_access_api_key`` de
acordo com os valores obtidos em `manager.scielo.org <http://manager.scielo.org/accounts/myaccount/#api_keys>`_.


Instale as dependências::

    # executar os comandos no diretório raíz do pacote/repositório
    pip install -r requirements.txt && python setup.py install


Execução
--------

Após a instalação, você pode executar uma instância da aplicação com o comando::

    pserve production.ini


Configurações do servidor de aplicação, como IP e porta da interface em escuta,
podem ser realizadas no arquivo *production.ini*.


Sobre o formato ID
------------------
http://bvsmodelo.bvsalud.org/download/cisis/CISIS-ManualReferencia-pt-5.2.pdf
(página 139)

    • !ID nnnnnn Marca de começo de registro com mfn=nnnnnn
    • !vnnn  Marca de começo de uma ocorrência do campo com tag nnn.


O arquivo terá a forma::

    !ID nnnnnn
    !vXXX!...conteúdo da tag XXX.............
    !vYYY!...conteúdo da tag YYY.............
    ...
    !ID nnnnnj
    !vXXQ!...conteúdo da tag XXQ.............
    !vYYQ!...conteúdo da tag YYQ.............
    ...


FAQ:
    * A codificação do arquivo ID deve ser ASCII, conforme consta na
      documentação da Bireme?

      **R:** Não, é possível que seja CP-1252.

    * Existe uma maneira de delegarmos a criação do mfn para o CISIS?

      **R:** Sim. Pode-se utilizar a sintaxe ``!ID 0`` para todos os registros
      e no utilitário id2i utilizar a opção ``app``::

        id2i arq.id create/app=i
